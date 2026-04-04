def build(
    query: str,
    files: list[dict]
) -> str:
    """
    Builds the RAG prompt for answering questions
    based on file contents.
    """
    context = ""
    for i, f in enumerate(files, 1):
        content = (
            f['extracted_text'][:2000]
            if f.get('extracted_text')
            else f['file_description']
        )
        context += f"""
                    File {i}: {f['filename']}
                    Path: {f['file_path']}
                    Content: {content}"""

    return f"""You are a helpful assistant that answers questions based on
            the user's personal files. Answer based ONLY on the provided file contents.
            If the answer is not in the files, say "I couldn't find relevant information
            in your files."

            Always mention which specific files you used to answer.
            Be concise but complete.

            FILES:
            {context}

            QUESTION: {query}

            Answer based on the files above:"""