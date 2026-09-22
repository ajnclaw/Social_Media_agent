# image_gen.py
#
# SD1.5 (photoreal fine-tune) + LCM-LoRA image generation. Lives in
# its own module so it can run standalone on a separate machine (see
# image_server.py) -- create_video calls this over HTTP instead of
# loading the model in-process, so it doesn't compete with Chatterbox
# for the same limited GPU memory.
#
# LCM-LoRA replaces SD-Turbo's own distillation: same few-step, fast
# generation, but layered on top of a photoreal-tuned base checkpoint
# instead of the base SD2.1 Turbo model, for noticeably better detail
# at a similar step count/speed (higher VRAM cost though -- ~4.2GB vs
# ~3.1GB, measured).

import os

import torch


# Override with IMAGE_MODEL_ID in .env to swap the base checkpoint
# without touching code.
IMAGE_MODEL_ID = os.environ.get(
    "IMAGE_MODEL_ID", "SG161222/Realistic_Vision_V6.0_B1_noVAE"
)
IMAGE_LORA_ID = "latent-consistency/lcm-lora-sdv1-5"
IMAGE_WIDTH = 576
IMAGE_HEIGHT = 1024
IMAGE_STEPS = 4
IMAGE_GUIDANCE = 1.5
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
        from diffusers import AutoPipelineForText2Image, LCMScheduler

        pipe = AutoPipelineForText2Image.from_pretrained(
            IMAGE_MODEL_ID,
            torch_dtype=torch.float16,
        )
        pipe.load_lora_weights(IMAGE_LORA_ID)
        pipe.scheduler = LCMScheduler.from_config(pipe.scheduler.config)

        _pipe = pipe.to("cuda")

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
