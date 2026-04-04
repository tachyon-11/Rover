import json
import logging
import ollama
from backend.schemas.organize import FolderTaxonomy, OrganizationPlan

logger = logging.getLogger(__name__)
MODEL = "llama3.2"

def generate_file_description(
    filename: str,
    extracted_text: str,
    metadata: dict
) -> str:
    #Doing as running on local so machine cant support too much load
    truncated_text = extracted_text[:10000] if extracted_text else ""

    clean_metadata = {
        k: v for k, v in metadata.items()
        if k in [
            "Content-Type",
            "Author",
            "Creation-Date",
            "title",
            "dc:title",
            "meta:word-count",
            "xmpTPg:NPages"
        ]
    }

    prompt = f"""You will be provided with the contents of a file along with its metadata. Provide a summary of the contents. The purpose of the summary is to organize and rename files based on their content. To this end provide a concise but informative summary. Make the summary as specific to the file as possible and try to include important data that was in file in Content Preview and metaData that might come useful in naming. Try to have description in such a way that if user reads it, they can have good idea about what info is inside file and can decide where to put it just by looking at description without opening file, also keep in mind it will also be used to provide context to LLM when it is making decision about where to put file so include any info that you think might be useful for that in description.

Filename: {filename}
Metadata: {clean_metadata}
Content preview: {truncated_text}

Respond with ONLY the summary, no preamble or explanation."""

    try:
        logger.info(f"Generating description for: {filename}")
        response = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        description = (response.message.content or "").strip()
        logger.info(f"Description generated for: {filename}")
        return description
    except Exception as e:
        logger.error(f"LLM error for {filename}: {e}")
        return f"File: {filename}"


def generate_folder_taxonomy(
    files: list[dict],
    existing_folders: list[str]
) -> FolderTaxonomy:
    files_text = "\n".join([
        f"- {f['filename']}: {f['file_description'][:200]}"
        for f in files
    ])

    existing_text = (
        "\n".join(existing_folders)
        if existing_folders
        else "None yet — this is the first organization run"
    )

    prompt = f"""You are a file organization expert.

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

    try:
        logger.info(f"Generating taxonomy for {len(files)} files...")
        response = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            format=FolderTaxonomy.model_json_schema()  # ← structured output
        )
        taxonomy = FolderTaxonomy.model_validate_json(
            response.message.content or "{}"
        )
        logger.info(f"Taxonomy: {[f.category for f in taxonomy.folders]}")
        return taxonomy
    except Exception as e:
        logger.error(f"Taxonomy generation error: {e}")
        raise

def assign_files_to_taxonomy(
    files: list[dict],
    taxonomy: FolderTaxonomy,
    file_type_map: dict
) -> OrganizationPlan:
    # Build taxonomy text for prompt
    taxonomy_text = ""
    for folder in taxonomy.folders:
        taxonomy_text += f"\n{folder.category}/\n"
        for sub in folder.subcategories:
            taxonomy_text += f"  └── {sub}/\n"

    # Build file list with type folder hint
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

        prompt = f"""You are a file organization assistant.

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

    try:
        logger.info(f"Assigning {len(files)} files to taxonomy...")
        response = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            format=OrganizationPlan.model_json_schema()  # ← structured output
        )
        plan = OrganizationPlan.model_validate_json(
            response.message.content or "{}"
        )
        logger.info(f"Assigned {len(plan.files)} files")
        return plan
    except Exception as e:
        logger.error(f"File assignment error: {e}")
        raise