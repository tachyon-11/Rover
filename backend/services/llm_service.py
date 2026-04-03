import logging
import ollama

logger = logging.getLogger(__name__)

MODEL = "llama3.2"

def generate_file_description(
    filename: str,
    extracted_text: str,
    metadata: dict
) -> str:
    # Truncate text —> Doing for my hardware limitation 
    truncated_text = extracted_text[:2000] if extracted_text else ""

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

    prompt = f"""You will be provided with the contents of a file along with its metadata.
Provide a summary of the contents. The purpose of the summary is to organize files based 
on their content. To this end provide a concise but informative summary. Make the summary 
as specific to the file as possible.

Filename: {filename}
Metadata: {clean_metadata}
Content preview:
{truncated_text}

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