from typing import List, Dict


def format_image_labels(image_labels: List[Dict]) -> str:
    """
    Format image classification/captioning results into human-readable text.

    Args:
        image_labels: List of label dictionaries with 'label', 'category', 'confidence' keys

    Returns:
        Formatted string representation of the image labels
    """
    if not image_labels:
        return "No objects detected"

    for item in image_labels:
        if isinstance(item, dict) and item.get("category") == "summary":
            return item.get("label", "")

    lines = []
    captions = [
        x["label"]
        for x in image_labels
        if isinstance(x, dict) and x.get("category") == "caption"
    ]
    if captions:
        lines.append(f"Caption: {captions[0]}")

    for item in image_labels:
        if isinstance(item, dict) and "category" in item:
            category = item.get("category")
            if category not in ("caption", "summary"):
                lines.append(
                    f"{item['label']} ({item['category']}, {item['confidence']:.0%})"
                )

    return "\n".join(lines) if lines else "No classifiable content"
