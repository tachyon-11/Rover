def build(
    question: str,
    files: list[dict],
    history: list[dict]
) -> str: 
    history_text = ""
    if history:
        history_text = "\nCONVERSATION HISTORY:\n"
        for msg in history:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_text += f"{role}: {msg['content']}\n"
        history_text += "\n"

    # Build file context
    context = ""
    for i, f in enumerate(files, 1):
        content = (
            f['extracted_text'][:3000]
            if f.get('extracted_text')
            else f['file_description']
        )
        context += f"""
                    File {i}: {f['filename']}
                    Path: {f['file_path']}
                    Content: {content}
                    ---"""

    return f"""You are a helpful personal assistant that answers questions
            based on the user's files. You have access to their documents and can
            answer questions about their content.

            STRICT RULES:
            - Answer ONLY based on the provided files
            - If the answer is not in the files say exactly:
              "I couldn't find information about that in your files."
            - Never make up or hallucinate information
            - Always cite which file(s) you used
            - Use conversation history for context on follow-up questions
            - Be concise but complete
            {history_text}
            AVAILABLE FILES:
            {context}

            CURRENT QUESTION: {question}

            Answer (cite your sources):"""