"""
faq-004/005/014/019/023/024/027/028/030/039/057/071 の answer に
バージョン確認・アップデートのステップを追加するパッチスクリプト
"""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PATH = "data/faq/faq_master.json"

NEW_STEP_TEXT = (
    "上記の対応で不具合が解消しない場合は、必ずロボットのアプリバージョンを確認し、"
    "最新でない場合はアップデートを行って改善するか試してください。"
    "最新バージョンであるにもかかわらず改善しない場合や、"
    "お客様側でWi-Fi環境の準備がどうしても困難な場合は、"
    "**伊藤電機へ対応を依頼（エスカレーション）**してください。"
)

def new_step(num_char):
    return f"{num_char} バージョン確認とアップデート: {NEW_STEP_TEXT}"

# ── 各FAQの編集定義 ──────────────────────────────────────────────
# (faq_id, 操作種別, 引数...)
# 操作種別:
#   "insert_before_unnumbered" : 番号なしエスカレーション段落の直前に挿入
#   "insert_before_step"       : 指定ステップ番号の直前に挿入し、そのステップを繰り上げ
#   "append"                   : 末尾に追加

PATCHES = [
    # faq-004: ⑤の後、番号なしエスカレーション段落の前に ⑥ を挿入
    {
        "id": "faq-004",
        "op": "insert_before_unnumbered",
        "new_num": "⑥",
        "marker": "解決しない場合は、**【共通：伊藤電機エスカレーション】",
    },
    # faq-005: ⑦の後（⑦内に条件付きエスカレーション）に ⑧ を追加
    {
        "id": "faq-005",
        "op": "append",
        "new_num": "⑧",
    },
    # faq-014: ⑤の後（⑤内に条件付きエスカレーション）に ⑥ を追加
    {
        "id": "faq-014",
        "op": "append",
        "new_num": "⑥",
    },
    # faq-019: ⑦の後（エスカレーションなし）に ⑧ を追加
    {
        "id": "faq-019",
        "op": "append",
        "new_num": "⑧",
    },
    # faq-023: ⑥（故障判断）の前に ⑦ を挿入し、旧⑥→⑦ に繰り上げ
    {
        "id": "faq-023",
        "op": "insert_before_step",
        "new_num": "⑦",
        "old_step_prefix": "⑥ 故障判断:",
        "old_step_new_prefix": "⑦ 故障判断:",
    },
    # faq-024: ⑤（エスカレーション）の前に ⑤ を挿入し、旧⑤→⑥ に繰り上げ
    {
        "id": "faq-024",
        "op": "insert_before_step",
        "new_num": "⑤",
        "old_step_prefix": "⑤ エスカレーション:",
        "old_step_new_prefix": "⑥ エスカレーション:",
    },
    # faq-027: ⑦（故障判断）の前に ⑦ を挿入し、旧⑦→⑧ に繰り上げ
    {
        "id": "faq-027",
        "op": "insert_before_step",
        "new_num": "⑦",
        "old_step_prefix": "⑦ 故障判断:",
        "old_step_new_prefix": "⑧ 故障判断:",
    },
    # faq-028: ④（エスカレーション）の前に ④ を挿入し、旧④→⑤ に繰り上げ
    {
        "id": "faq-028",
        "op": "insert_before_step",
        "new_num": "④",
        "old_step_prefix": "④ エスカレーション:",
        "old_step_new_prefix": "⑤ エスカレーション:",
    },
    # faq-030: ⑥（エスカレーション）の前に ⑥ を挿入し、旧⑥→⑦ に繰り上げ
    {
        "id": "faq-030",
        "op": "insert_before_step",
        "new_num": "⑥",
        "old_step_prefix": "⑥ エスカレーション:",
        "old_step_new_prefix": "⑦ エスカレーション:",
    },
    # faq-039: ⑤（エスカレーション）の前に ⑤ を挿入し、旧⑤→⑥ に繰り上げ
    {
        "id": "faq-039",
        "op": "insert_before_step",
        "new_num": "⑤",
        "old_step_prefix": "⑤ エスカレーション:",
        "old_step_new_prefix": "⑥ エスカレーション:",
    },
    # faq-057: ⑤（エスカレーション）の前に ⑤ を挿入し、旧⑤→⑥ に繰り上げ
    {
        "id": "faq-057",
        "op": "insert_before_step",
        "new_num": "⑤",
        "old_step_prefix": "⑤ エスカレーション:",
        "old_step_new_prefix": "⑥ エスカレーション:",
    },
    # faq-071: ⑤（エスカレーション）の前に ⑤ を挿入し、旧⑤→⑥ に繰り上げ
    {
        "id": "faq-071",
        "op": "insert_before_step",
        "new_num": "⑤",
        "old_step_prefix": "⑤ エスカレーション:",
        "old_step_new_prefix": "⑥ エスカレーション:",
    },
]

with open(PATH, encoding="utf-8") as f:
    data = json.load(f)

patch_map = {p["id"]: p for p in PATCHES}
patched = []

for item in data["items"]:
    fid = item["id"]
    if fid not in patch_map:
        patched.append(item)
        continue

    p = patch_map[fid]
    answer = item["answer"]
    ns = new_step(p["new_num"])

    if p["op"] == "insert_before_unnumbered":
        marker = p["marker"]
        idx = answer.find(marker)
        if idx == -1:
            print(f"[WARN] {fid}: marker not found")
        else:
            answer = answer[:idx] + ns + "\n" + answer[idx:]
            print(f"[OK] {fid}: inserted {p['new_num']} before unnumbered escalation")

    elif p["op"] == "insert_before_step":
        old_prefix = p["old_step_prefix"]
        new_prefix = p["old_step_new_prefix"]
        if old_prefix not in answer:
            print(f"[WARN] {fid}: old_step_prefix not found: {old_prefix}")
        else:
            # 旧ステップの番号を繰り上げ
            answer = answer.replace(old_prefix, new_prefix, 1)
            # 繰り上げ後のマーカーの前に新ステップを挿入
            idx = answer.find(new_prefix)
            answer = answer[:idx] + ns + "\n" + answer[idx:]
            print(f"[OK] {fid}: inserted {p['new_num']}, renumbered to {new_prefix}")

    elif p["op"] == "append":
        answer = answer + "\n" + ns
        print(f"[OK] {fid}: appended {p['new_num']} at end")

    item["answer"] = answer
    patched.append(item)

data["items"] = patched

with open(PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("\n[DONE] faq_master.json updated.")
