def build(
    files: list[dict],
    existing_folders: list[str]
) -> str:
    files_text = "\n".join([
        f"- {f['filename']}: {f['file_description'][:200]}"
        for f in files
    ])

    existing_text = (
        "\n".join(existing_folders)
        if existing_folders
        else "None yet — this is the first organization run"
    )

    return f"""You are a file organization expert.
            Below is a list of files with their descriptions, and the existing folder structure.
            Your job is to design a master folder taxonomy that:
            - Creates new folders only when truly needed
            - Groups related files logically by topic and purpose
            - Uses clear, consistent naming conventions
            - Each category must have 2-4 subcategories — no empty subcategories
            - NO duplicate categories — each category must be unique
            - Categories must be broad and reusable
            - Subcategory should be specific type within topic to drilldown specific group of files location based on their use case
            - Inside subcategory keep it simple just based on file types as given in map
            - Think about relationships between files — group related files together
            - Use context clues like names, companies, institutions to identify topics
            - REUSES existing folders where appropriate — don't create duplicates

            Existing folder structure (REUSE these) by this I mean try to fit files which might easily fall into them based on their description into those folders instead of creating new ones:
            {existing_text}

            Files to organize:
            {files_text}

            Design the complete folder taxonomy."""