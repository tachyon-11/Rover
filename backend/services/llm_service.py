import logging
import ollama
import json

logger = logging.getLogger(__name__)

MODEL = "llama3.2"

def generate_file_description(
    filename: str,
    extracted_text: str,
    metadata: dict
) -> str:
    # Truncate text —> Doing for my hardware limitation 
    truncated_text = extracted_text[:10000] if extracted_text else ""

    # Clean up metadata — only send useful fields
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
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        description = (response.message.content or "").strip()
        logger.info(f"Description generated for: {filename}")
        return description

    except Exception as e:
        logger.error(f"LLM error for {filename}: {e}")
        return f"File: {filename}"
      
def batch_organize_files(files: list[dict]) -> list[dict]:
    """
    Takes a batch of files with their descriptions.
    LLM proposes new folder structure + filenames for all.
    """

    # Build file list for prompt
    files_text = ""
    for i, f in enumerate(files, 1):
        files_text += f"""
          File {i}:
          - ID: {f['file_id']}
          - Current filename: {f['filename']}
          - File type: {f['file_type']}
          - Description: {f['file_description']}
          ---"""

    prompt = f"""You will be provided with a list of files and their descriptions.
    For each file, propose a new path and filename that optimally organizes them.

    You are organizing files for a user. Use context clues from ALL files together
    to identify relationships and group related files logically.

    Follow these guidelines:
    - Think about relationships between files — group related files together
    - Use context to identify topics (e.g. course names, project names, companies)
    - Use versioning : Are you maintaining different versions of the same file?
    - Based on use case try to add some data to filename if it can help user identify content of file just by looking at name without opening it
    - Structure: Category/Subcategory/FileType/filename.ext
      - Category: broad topic (This should be the most general grouping, e.g. which woiuld give a broad idea about what all the docs inside have info about")
      - Subcategory: type within topic (e.g. "Notes", "Assignments", "Invoices", "Reports")
      - FileType: based on format (Documents, Spreadsheets, Presentations, Text)
      - filename: descriptive, no spaces, use underscores, include date if available
    - Use good naming conventions:
      - No spaces or special characters in filenames
      - Use underscores to separate words
      - Include dates in YYYY_MM format if available
      - Abbreviate long names sensibly
      - Use versioning if multiple versions exist (v1, v2)
    - Be specific and consistent across related files
    If the file is already named well or matches a known convention, set the destination path to the same as the source path.

    Files to organize:
    {files_text}

    Respond with ONLY a valid JSON array, no explanation, no markdown, no backticks.
    Format exactly like this:
    [
      {{
        "file_id": "exact-uuid-from-above",
        "original_filename": "original name",
        "new_path": "Category/Subcategory/FileType/new_filename.ext"
      }}
    ]"""

    try:
        logger.info(f"Batch organizing {len(files)} files...")

        response = ollama.chat(
            model=MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        content = (response.message.content or "").strip()

        # Clean up response — remove markdown if present
        content = content.replace("```json", "").replace("```", "").strip()

        # Parse JSON
        result = json.loads(content)
        logger.info(f"Batch organize complete: {len(result)} files organized")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON: {e}")
        logger.error(f"Raw response: {content}")
        raise
    except Exception as e:
        logger.error(f"Batch organize error: {e}")
        raise