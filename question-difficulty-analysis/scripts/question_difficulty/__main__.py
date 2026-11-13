import argparse
import json
import sys
from pathlib import Path
from .engine import score_question, score_paper, ValidationError


def score_input(data, scope="auto"):
    """Select report scope without changing the scoring rules."""
    if not isinstance(data, dict):
        raise ValidationError("input must be an object")
    if data.get("algorithm", "HCT-rules-v1.1") != "HCT-rules-v1.1":
        raise ValidationError("unsupported algorithm; do not silently relabel another version")
    if "parameters" in data:
        from export_report import PARAMETERS
        if data["parameters"] != PARAMETERS:
            raise ValidationError("custom parameters unsupported by this fixed engine")
    if scope not in ("auto", "question", "paper", "group"):
        raise ValidationError("unknown scope")
    if "questions" not in data:
        if scope == "paper":
            raise ValidationError("paper scope requires a questions array")
        return {"algorithm": "HCT-rules-v1.1", "engine": "0.1.2",
                "scope": "question", "question": score_question(data)}
    if "steps" in data:
        raise ValidationError("ambiguous input: both steps and questions")
    selected = data.get("scope", "paper") if scope == "auto" else scope
    if selected not in ("question", "paper", "group"):
        raise ValidationError("scope must be question, paper or group")
    papers = {q.get("paper_id", data.get("paper_id")) for q in data["questions"]}
    years = {q.get("year") for q in data["questions"] if q.get("year") is not None}
    if len(papers) > 1 or len(years) > 1:
        raise ValidationError("mixed papers/years: score each paper separately")
    result = score_paper(data["questions"])
    if selected == "question":
        stats = result["statistics"]
        stats["whole_question_weighted_mean"] = stats.pop("whole_paper_weighted_mean")
        stats["weighted_scope"] = stats["weighted_scope"].replace("整卷", "整题")
    if selected == "group":
        stats = result["statistics"]
        stats["provided_group_weighted_mean"] = stats.pop("whole_paper_weighted_mean")
        stats["weighted_scope"] = stats["weighted_scope"].replace("整卷", "所提供题组")
    result["scope"] = selected
    return result


def main():
    parser = argparse.ArgumentParser(description="复算有依据的H/C/T/D规则分；不自动解题或预测得分率。")
    parser.add_argument("input", type=Path, help="单小问对象，或含questions数组的JSON文件")
    parser.add_argument("--scope", choices=("auto", "question", "paper", "group"), default="auto",
                        help="分析范围；多小问单题可设question；旧数组默认paper")
    parser.add_argument("--output", type=Path, help="结果JSON；省略则输出到终端")
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding="utf-8-sig"))
        result = score_input(data, args.scope)
        result["input_snapshot"] = data
        result["snapshot_note"] = "原始输入保留供追溯；其中历史分数不是本次复算结果，以顶层 question/questions 为准。"
        text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
        if args.output:
            if args.output.resolve() == args.input.resolve():
                raise ValidationError("output must not overwrite the input evidence")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text+"\n", encoding="utf-8")
        else:
            print(text)
    except (OSError, ValueError, TypeError) as exc:
        print(f"输入或计算错误：{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
