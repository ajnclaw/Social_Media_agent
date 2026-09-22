# image_gen.py
#
# SD-Turbo image generation. Lives in its own module so it can run
# standalone on a separate machine (see image_server.py) -- create_video
# calls this over HTTP instead of loading the model in-process, so it
# doesn't compete with Chatterbox for the same limited GPU memory.

import os

import torch


# Override with IMAGE_MODEL_ID in .env to swap models without touching
# code -- e.g. "stabilityai/sdxl-turbo" for higher quality at the cost
# of more VRAM and a slower generate step.
IMAGE_MODEL_ID = os.environ.get("IMAGE_MODEL_ID", "stabilityai/sd-turbo")
IMAGE_WIDTH = 576
IMAGE_HEIGHT = 1024
IMAGE_STEPS = 4
IMAGE_GUIDANCE = 1.8
IMAGE_REALISM_SUFFIX = (
    "photorealistic, natural lighting, realistic detail, shot on 35mm "
    "film, shallow depth of field, documentary photography, 8k uhd"
)
IMAGE_NEGATIVE_PROMPT = (
    "cartoon, illustration, painting, cgi, render, plastic skin, "
    "over-saturated, deformed, blurry, low quality, uncanny"
)

_pipe = None


def _load_pipeline():
    global _pipe

    if _pipe is None:
        from diffusers import AutoPipelineForText2Image

        _pipe = AutoPipelineForText2Image.from_pretrained(
            IMAGE_MODEL_ID,
            torch_dtype=torch.float16,
            variant="fp16",
        ).to("cuda")

    return _pipe


def generate_image(prompt):
    pipe = _load_pipeline()

    return pipe(
        prompt=f"{prompt}, {IMAGE_REALISM_SUFFIX}",
        negative_prompt=IMAGE_NEGATIVE_PROMPT,
        num_inference_steps=IMAGE_STEPS,
        guidance_scale=IMAGE_GUIDANCE,
        height=IMAGE_HEIGHT,
        width=IMAGE_WIDTH,
    ).images[0]
