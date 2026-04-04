from backend.schemas.organize import FolderTaxonomy


def build(
    files: list[dict],
    taxonomy: FolderTaxonomy,
    file_type_map: dict
) -> str:
    taxonomy_text = ""
    for folder in taxonomy.folders:
        taxonomy_text += f"\n{folder.category}/\n"
        for sub in folder.subcategories:
            taxonomy_text += f"  └── {sub}/\n"

    files_text = ""
    for f in files:
        file_type_folder = file_type_map.get(
            f['file_type'], 'Documents'
        )
        files_text += f"""
                          File ID: {f['file_id']}
                          Filename: {f['filename']}
                          File type folder: {file_type_folder}
                          Description: {f['file_description'][:400]}
                      """

    return f"""You are a file organization assistant.

            Assign each file to the most appropriate location in this taxonomy.
            The file type folder is the last level before the filename.

            MASTER TAXONOMY (use ONLY these — do not invent new folders):
            {taxonomy_text}

            NAMING RULES:
            - NO spaces in filenames — use underscores only
            - NO special characters or leading hyphens
            - Include dates in YYYY_MM format if known
            - Be descriptive — user should understand file content from name alone
            - Add relevant metadata to filename (person name, company, date, version)
            - Use versioning if multiple versions exist (v1, v2)
            - Structure: Category/Subcategory/FileTypeFolder/filename.ext

            FILES TO ASSIGN:
            {files_text}

            Assign EVERY file. Use the EXACT file IDs provided."""