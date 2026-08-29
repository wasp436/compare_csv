#!/usr/bin/env python3
import argparse
import csv
import string
import sys
from difflib import SequenceMatcher


def col_letter(index: int) -> str:
    letters = ""
    index += 1
    while index > 0:
        index, rem = divmod(index - 1, 26)
        letters = string.ascii_uppercase[rem] + letters
    return letters


def read_csv(path, encoding, delimiter):
    with open(path, newline="", encoding=encoding) as f:
        reader = csv.reader(f, delimiter=delimiter)
        return [row for row in reader]


def format_row(row):
    return ",".join(row)


def resolve_key_index(header, key):
    if key in header:
        return header.index(key)
    try:
        idx = int(key)
    except ValueError:
        raise ValueError(f"找不到欄位 {key!r}，且它也不是有效的欄位編號（從 0 開始）")
    if idx < 0 or idx >= len(header):
        raise ValueError(f"欄位編號 {idx} 超出範圍（標題列共有 {len(header)} 欄）")
    return idx


def index_by_key(data, key_index):
    index = {}
    for i, row in enumerate(data):
        key = row[key_index] if key_index < len(row) else ""
        index.setdefault(key, []).append((i, row))
    return index


def compare_by_key(rows_a, rows_b, key_index_a, key_index_b):
    data_a, data_b = rows_a[1:], rows_b[1:]
    idx_a = index_by_key(data_a, key_index_a)
    idx_b = index_by_key(data_b, key_index_b)

    ordered_keys = []
    seen = set()
    for row in data_a:
        k = row[key_index_a] if key_index_a < len(row) else ""
        if k not in seen:
            seen.add(k)
            ordered_keys.append(k)
    for row in data_b:
        k = row[key_index_b] if key_index_b < len(row) else ""
        if k not in seen:
            seen.add(k)
            ordered_keys.append(k)

    diffs = []
    for k in ordered_keys:
        a_entries = idx_a.get(k, [])
        b_entries = idx_b.get(k, [])

        for (i_a, row_a), (i_b, row_b) in zip(a_entries, b_entries):
            max_len = max(len(row_a), len(row_b))
            for c in range(max_len):
                val_a = row_a[c] if c < len(row_a) else ""
                val_b = row_b[c] if c < len(row_b) else ""
                if val_a != val_b:
                    diffs.append({
                        "type": "modified",
                        "cell": f"{col_letter(c)}{i_a + 2}",
                        "csv1_row": i_a + 2,
                        "csv2_row": i_b + 2,
                        "csv1_value": val_a,
                        "csv2_value": val_b,
                    })

        for i_a, row_a in a_entries[len(b_entries):]:
            diffs.append({
                "type": "removed",
                "csv1_row": i_a + 2,
                "csv1_value": format_row(row_a),
            })
        for i_b, row_b in b_entries[len(a_entries):]:
            diffs.append({
                "type": "added",
                "csv2_row": i_b + 2,
                "csv2_value": format_row(row_b),
            })

    return diffs


def compare(rows_a, rows_b):
    a_key = [tuple(r) for r in rows_a]
    b_key = [tuple(r) for r in rows_b]
    sm = SequenceMatcher(a=a_key, b=b_key, autojunk=False)

    diffs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue

        if tag == "replace" and (i2 - i1) == (j2 - j1):
            for offset in range(i2 - i1):
                a_idx = i1 + offset
                b_idx = j1 + offset
                row_a = rows_a[a_idx]
                row_b = rows_b[b_idx]
                max_len = max(len(row_a), len(row_b))
                for c in range(max_len):
                    val_a = row_a[c] if c < len(row_a) else ""
                    val_b = row_b[c] if c < len(row_b) else ""
                    if val_a != val_b:
                        diffs.append({
                            "type": "modified",
                            "cell": f"{col_letter(c)}{a_idx + 1}",
                            "csv1_row": a_idx + 1,
                            "csv2_row": b_idx + 1,
                            "csv1_value": val_a,
                            "csv2_value": val_b,
                        })
        else:
            for a_idx in range(i1, i2):
                diffs.append({
                    "type": "removed",
                    "csv1_row": a_idx + 1,
                    "csv1_value": format_row(rows_a[a_idx]),
                })
            for b_idx in range(j1, j2):
                diffs.append({
                    "type": "added",
                    "csv2_row": b_idx + 1,
                    "csv2_value": format_row(rows_b[b_idx]),
                })
    return diffs


def main():
    parser = argparse.ArgumentParser(description="比較兩個 CSV 檔案的差異")
    parser.add_argument("csv1")
    parser.add_argument("csv2")
    parser.add_argument("--encoding", default="utf-8-sig", help="檔案編碼，例如 utf-8-sig 或 big5")
    parser.add_argument("--delimiter", default=",", help="欄位分隔符號，預設為逗號")
    parser.add_argument("--output", default="diff.csv", help="將結果輸出成 CSV 檔（預設 diff.csv，填空字串可關閉輸出）")
    parser.add_argument("--key", default="ID", help="用來配對兩邊列的欄位名稱（或從 0 開始的欄位編號），預設 ID，填空字串可關閉並改用整列內容比對")
    args = parser.parse_args()

    try:
        rows_a = read_csv(args.csv1, args.encoding, args.delimiter)
        rows_b = read_csv(args.csv2, args.encoding, args.delimiter)
    except UnicodeDecodeError as e:
        print(f"讀取檔案時發生編碼錯誤：{e}\n請嘗試加上 --encoding big5 或 --encoding utf-8", file=sys.stderr)
        sys.exit(1)

    if args.key:
        try:
            key_index_a = resolve_key_index(rows_a[0], args.key)
        except ValueError as e:
            print(f"{args.csv1}：{e}", file=sys.stderr)
            sys.exit(1)
        try:
            key_index_b = resolve_key_index(rows_b[0], args.key)
        except ValueError as e:
            print(f"{args.csv2}：{e}", file=sys.stderr)
            sys.exit(1)
        diffs = compare_by_key(rows_a, rows_b, key_index_a, key_index_b)
    else:
        diffs = compare(rows_a, rows_b)

    print(f"{args.csv1}：共 {len(rows_a)} 列")
    print(f"{args.csv2}：共 {len(rows_b)} 列")
    print(f"差異數量：{len(diffs)}\n")

    for d in diffs:
        if d["type"] == "modified":
            row_note = "" if d["csv1_row"] == d["csv2_row"] else f"（{args.csv2} 第{d['csv2_row']}列）"
            print(f"[修改] {d['cell']}{row_note}　{args.csv1} = {d['csv1_value']!r}　"
                  f"{args.csv2} = {d['csv2_value']!r}")
        elif d["type"] == "removed":
            print(f"[刪除] {args.csv1} 第{d['csv1_row']}列（{args.csv2} 沒有對應這一列）："
                  f"{d['csv1_value']}")
        elif d["type"] == "added":
            print(f"[新增] {args.csv2} 第{d['csv2_row']}列（{args.csv1} 沒有對應這一列）："
                  f"{d['csv2_value']}")

    if not diffs:
        print("兩個檔案內容完全相同。")

    if args.output:
        type_order = {"modified": 0, "removed": 1, "added": 2}
        sorted_diffs = sorted(diffs, key=lambda d: type_order[d["type"]])
        with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["類型", "儲存格", "CSV1值", "CSV2值", "備註"])
            for d in sorted_diffs:
                if d["type"] == "modified":
                    note = "" if d["csv1_row"] == d["csv2_row"] else f"CSV2 第{d['csv2_row']}列"
                    writer.writerow(["修改", d["cell"], d["csv1_value"], d["csv2_value"], note])
                elif d["type"] == "removed":
                    writer.writerow(["刪除", "", d["csv1_value"], "", f"CSV1 第{d['csv1_row']}列"])
                elif d["type"] == "added":
                    writer.writerow(["新增", "", "", d["csv2_value"], f"CSV2 第{d['csv2_row']}列"])
        print(f"\n已將結果輸出至 {args.output}")


if __name__ == "__main__":
    main()
