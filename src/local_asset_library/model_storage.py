"""Account only for this project's pinned revisions in shared model storage."""
import json


def project_model_bytes(config):
    total = 0
    for folder, contract_file in (("qwen3-vl-2b", "caption-model.json"),
                                  ("embeddinggemma-2", "embedding-model.json")):
        contract = json.loads((config.project_root / "docs" / contract_file).read_text(encoding="utf-8"))
        directory = config.output_path("models", folder + "/" + contract["revision"])
        for path in directory.rglob("*"):
            checked = config.output_path("models", path.relative_to(config.storage_root("models")).as_posix())
            if checked.is_file():
                total += checked.stat().st_size
    return total
