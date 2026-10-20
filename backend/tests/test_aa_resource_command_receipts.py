"""Real MySQL transactions: original receipts, versioned mapping and room exclusion."""
from concurrent.futures import ThreadPoolExecutor

from tests.test_aa_resource_ext import BASE, _hdr, _mk_classroom, _mk_lab


def test_lab_commands_keep_original_receipts_and_share_physical_occupancy(client, db_mode):
    headers = _hdr(client, "school_admin01")
    room_id = _mk_classroom(client, headers, "RC", "101", allowBorrow=True).json()["data"]["classroomId"]
    lab = _mk_lab(client, headers, "RC-LAB").json()["data"]
    lab_id = lab["labId"]
    binding_key = "resource-bind-original-001"
    binding = client.put(f"{BASE}/labs/{lab_id}/schedule-resource",
                         headers={**headers, "Idempotency-Key": binding_key},
                         json={"classroomId": room_id, "expectedVersion": lab["version"]})
    assert binding.status_code == 200, binding.text
    lab_version = binding.json()["data"]["version"]
    booking_key = "resource-book-original-001"
    body = {"labId": lab_id, "bookingDate": "2027-06-20", "slotNo": 1, "purpose": "隔离测试预约"}

    def send():
        return client.post(f"{BASE}/labs/bookings", headers={**headers, "Idempotency-Key": booking_key}, json=body)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _index: send(), range(2)))
    assert all(response.status_code == 200 for response in responses), [r.text for r in responses]
    booking_ids = {response.json()["data"]["bookingId"] for response in responses}
    assert len(booking_ids) == 1
    booking_id = booking_ids.pop()
    changed = client.post(f"{BASE}/labs/bookings", headers={**headers, "Idempotency-Key": booking_key},
                          json={**body, "purpose": "另一条命令不得复用原键"})
    assert changed.status_code == 409, changed.text

    review_key = "resource-review-original-001"
    review_body = {"action": "APPROVE", "expectedClassroomId": room_id, "expectedLabVersion": lab_version}
    stale = client.post(f"{BASE}/labs/bookings/{booking_id}/review",
                        headers={**headers, "Idempotency-Key": "resource-review-stale-001"},
                        json={**review_body, "expectedLabVersion": lab_version - 1})
    assert stale.status_code == 409, stale.text
    failed_receipt = client.get(f"{BASE}/resources/command-receipts/resource-review-stale-001",
                                headers=headers, params={"operation": "RESOURCE_LAB_REVIEW"})
    assert failed_receipt.json()["data"]["state"] == "UNRESOLVED"
    approved = client.post(f"{BASE}/labs/bookings/{booking_id}/review",
                           headers={**headers, "Idempotency-Key": review_key}, json=review_body)
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["classroomId"] == str(room_id)
    for command_key, operation, status in (
        (booking_key, "RESOURCE_LAB_BOOK", "PENDING"),
        (review_key, "RESOURCE_LAB_REVIEW", "APPROVED"),
    ):
        receipt = client.get(f"{BASE}/resources/command-receipts/{command_key}",
                             headers=headers, params={"operation": operation})
        assert receipt.status_code == 200, receipt.text
        result = receipt.json()["data"]
        assert result["state"] == "SUCCESS"
        assert result["result"]["bookingId"] == booking_id
        assert result["result"]["status"] == status

    classroom_booking = client.post(f"{BASE}/classrooms/bookings", headers=headers,
                                     json={"classroomId": room_id, "bookingDate": body["bookingDate"],
                                           "slotNo": 1, "purpose": "同一物理场地的另一来源"})
    assert classroom_booking.status_code == 200, classroom_booking.text
    other_id = classroom_booking.json()["data"]["bookingId"]
    blocked = client.post(f"{BASE}/classrooms/bookings/{other_id}/review", headers=headers,
                          json={"action": "APPROVE"})
    assert blocked.status_code == 409, blocked.text
    occupancy = client.get(f"{BASE}/resources/occupancy", headers=headers,
                            params={"date": body["bookingDate"], "resourceKind": "CLASSROOM"})
    assert occupancy.status_code == 200, occupancy.text
    assert any(row["bookingId"] == booking_id and row["bookingResourceKind"] == "LAB"
               and row["resourceId"] == str(room_id) for row in occupancy.json()["data"]["items"])
