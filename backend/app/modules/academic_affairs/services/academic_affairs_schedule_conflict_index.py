"""课表冲突候选分桶索引。

这里只优化“哪些课表行值得互相比对”，不定义任何冲突业务规则。调用方继续使用
canonical 周次重叠、教师/班级/教室优先级判断，避免出现第二套冲突检测器。
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator


def iter_same_slot_pairs(items: Iterable[object]) -> Iterator[tuple[object, object]]:
    """按 ``(weekday, slot_no)`` 分桶后，以旧实现的全局 pair 顺序产出候选。

    旧实现会枚举整批 ``n*(n-1)/2`` 对，再丢弃不同星期/节次的 pair。这里先建 O(n)
    索引，每个 left 只扫描自己的槽位后缀；仍保持“先 left 全局顺序、再 right 全局顺序”，
    因此 hardConflicts 的既有输出顺序不会因性能优化发生漂移。
    """
    rows = list(items)
    buckets: dict[tuple[object, object], list[object]] = defaultdict(list)
    bucket_positions: list[int] = []

    for item in rows:
        key = (getattr(item, "weekday", None), getattr(item, "slot_no", None))
        bucket = buckets[key]
        bucket_positions.append(len(bucket))
        bucket.append(item)

    for index, left in enumerate(rows):
        key = (getattr(left, "weekday", None), getattr(left, "slot_no", None))
        bucket = buckets[key]
        for right in bucket[bucket_positions[index] + 1 :]:
            yield left, right
