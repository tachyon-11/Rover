import logging
import ollama
from backend.schemas.organize import FolderTaxonomy, OrganizationPlan
from backend.prompts import PromptType
from backend.prompts import description, taxonomy, assignment

logger = logging.getLogger(__name__)
MODEL = "llama3.2"


def generate_file_description(
    filename: str,
    extracted_text: str,
    metadata: dict
) -> str:
    prompt = description.build(
        filename=filename,
        extracted_text=extracted_text,
        metadata=metadata
    )

    try:
        logger.info(
            f"[{PromptType.DESCRIPTION.value}] "
            f"Generating description for: {filename}"
        )
        response = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        result = (response.message.content or "").strip()
        logger.info(f"Description generated for: {filename}")
        return result
    except Exception as e:
        logger.error(f"LLM error for {filename}: {e}")
        return f"File: {filename}"


def generate_folder_taxonomy(
    files: list[dict],
    existing_folders: list[str]
) -> FolderTaxonomy:
    prompt = taxonomy.build(
        files=files,
        existing_folders=existing_folders
    )

    try:
        logger.info(
            f"[{PromptType.TAXONOMY.value}] "
            f"Generating taxonomy for {len(files)} files..."
        )
        response = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            format=FolderTaxonomy.model_json_schema()
        )
        result = FolderTaxonomy.model_validate_json(
            response.message.content or "{}"
        )
        logger.info(f"Taxonomy: {[f.category for f in result.folders]}")
        return result
    except Exception as e:
        logger.error(f"Taxonomy generation error: {e}")
        raise


def assign_files_to_taxonomy(
    files: list[dict],
    taxonomy_data: FolderTaxonomy,
    file_type_map: dict
) -> OrganizationPlan:
    prompt = assignment.build(
        files=files,
        taxonomy=taxonomy_data,
        file_type_map=file_type_map
    )

    try:
        logger.info(
            f"[{PromptType.ASSIGNMENT.value}] "
            f"Assigning {len(files)} files..."
        )
        response = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            format=OrganizationPlan.model_json_schema()
        )
        result = OrganizationPlan.model_validate_json(
            response.message.content or "{}"
        )
        logger.info(f"Assigned {len(result.files)} files")
        return result
    except Exception as e:
        logger.error(f"File assignment error: {e}")
        raise