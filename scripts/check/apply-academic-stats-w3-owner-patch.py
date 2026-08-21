#!/usr/bin/env python3
"""Apply the minimal W3 mount to the existing large stats view, then self-delete via workflow."""
from pathlib import Path

PATH = Path("frontend/src/modules/academicAffairs/views/AaStatsOverviewView.vue")


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exact block once, found {count}: {old[:80]!r}")
    return text.replace(old, new, 1)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''      <div v-if="tab !== 'export' && tab !== 'resource'" class="aa-filter">''',
        '''      <div v-if="tab !== 'export' && tab !== 'resource' && tab !== 'snapshot'" class="aa-filter">''',
    )
    text = replace_once(
        text,
        '''        <!-- ══ 导出报表（15）══ -->\n        <template v-else-if="tab === 'export'">''',
        '''        <!-- ══ 统计冻结快照（W3）══ -->\n        <template v-else-if="tab === 'snapshot'">\n          <AaStatsSnapshotWorkspace :context-filters="filters" />\n        </template>\n\n        <!-- ══ 导出报表（15）══ -->\n        <template v-else-if="tab === 'export'">''',
    )
    text = replace_once(
        text,
        '''import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'\nimport { toast } from '@/utils/toast' ''',
        '''import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'\nimport AaStatsSnapshotWorkspace from '@/modules/academicAffairs/components/AaStatsSnapshotWorkspace.vue'\nimport { toast } from '@/utils/toast' ''',
    ) if "import { toast } from '@/utils/toast' " in text else replace_once(
        text,
        '''import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'\nimport { toast } from '@/utils/toast'\n''',
        '''import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'\nimport AaStatsSnapshotWorkspace from '@/modules/academicAffairs/components/AaStatsSnapshotWorkspace.vue'\nimport { toast } from '@/utils/toast'\n''',
    )
    text = replace_once(
        text,
        '''  { key: 'resource', label: '教学资源统计' },\n  { key: 'export', label: '导出报表' }''',
        '''  { key: 'resource', label: '教学资源统计' },\n  { key: 'snapshot', label: '统计快照' },\n  { key: 'export', label: '导出报表' }''',
    )
    text = replace_once(
        text,
        '''    AppCollegePicker, AppMajorPicker, AppGraduationBatchPicker\n  },''',
        '''    AppCollegePicker, AppMajorPicker, AppGraduationBatchPicker, AaStatsSnapshotWorkspace\n  },''',
    )
    text = replace_once(
        text,
        '''      } else if (this.tab === 'export') {\n        this.loading = false\n      } else {''',
        '''      } else if (this.tab === 'export' || this.tab === 'snapshot') {\n        this.loading = false\n      } else {''',
    )
    PATH.write_text(text, encoding="utf-8")
    print("W3 stats owner patch applied")


if __name__ == "__main__":
    main()
