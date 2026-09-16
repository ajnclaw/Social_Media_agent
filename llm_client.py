import ollama


def chat(component, model, messages, tools=None, logger=None):
    kwargs = {
        "model": model,
        "messages": messages,
    }

    if tools is not None:
        kwargs["tools"] = tools

    response = ollama.chat(**kwargs)

    if logger:
        logger.log_llm_call(component, model, response)

    return response