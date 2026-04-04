def build(
    filename: str,
    extracted_text: str,
    metadata: dict
) -> str:
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

    return f"""You will be provided with the contents of a file along with its metadata. Provide a summary of the contents. The purpose of the summary is to organize and rename files based on their content. To this end provide a concise but informative summary. Make the summary as specific to the file as possible and try to include important data that was in file in Content Preview and metaData that might come useful in naming. Try to have description in such a way that if user reads it, they can have good idea about what info is inside file and can decide where to put it just by looking at description without opening file, also keep in mind it will also be used to provide context to LLM when it is making decision about where to put file so include any info that you think might be useful for that in description.
    Filename: {filename}
    Metadata: {clean_metadata}
    Content preview: {truncated_text}

    Respond with ONLY the summary, no preamble or explanation."""