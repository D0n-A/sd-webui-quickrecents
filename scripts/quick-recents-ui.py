import modules.infotext_utils as parameters_copypaste
from modules import shared, errors
import modules.scripts as scripts
from functools import lru_cache
from heapq import nlargest
from PIL import Image
import gradio as gr
import os

allowed_ext = ('.png', '.jpg', '.jpeg', '.webp', '.avif')


@lru_cache(maxsize=128)
def create_fake_image(img_path):
    fake_image = Image.new(mode="RGB", size=(1, 1))
    fake_image.already_saved_as = img_path
    return fake_image


def scan_images(dir_path):
    for root, _, fns in os.walk(dir_path):
        for fn in fns:
            if fn.lower().endswith(allowed_ext):
                yield os.path.join(root, fn)


def get_recent_images(n, is_img2img):
    # Crawl through txt/img2img directories to find recent images
    img_dir = shared.opts.outdir_samples or (shared.opts.outdir_img2img_samples if is_img2img else shared.opts.outdir_txt2img_samples)
    return nlargest(n, scan_images(img_dir), key=os.path.getmtime)


def get_gallery_images(n, is_img2img):
    return [create_fake_image(img_path) for img_path in get_recent_images(n, is_img2img)]


def update_params(evt: gr.SelectData, images):
    try:
        image, q, timestamp = images[evt.index]['name'].rpartition('?')
        image_path = image if q else timestamp
        with Image.open(image_path) as img:
            metadata = img.info
        return metadata.get('parameters', '')
    except Exception:
        errors.report("Error reading image parameters", exc_info=True)
        return ''


class QuickRecentsScript(scripts.Script):
    # So the tap appears at the top
    sorting_priority = -5

    def __init__(self):
        super().__init__()
        self.recent_images = []
        self.num_img = 8
        self.num_cols = 2
        self.num_rows = (self.num_img + self.num_cols - 1) // self.num_cols
        self.is_img2img = None

    def title(self):
        return "Quick Recents"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def ui(self, is_img2img):
        self.is_img2img = is_img2img
        generation_info = gr.Textbox(visible=False)

        with gr.Accordion('Quick Recents', open=False):
            with gr.Row():
                apply = gr.Button('Apply', scale=19)
                parameters_copypaste.register_paste_params_button(parameters_copypaste.ParamBinding(
                    paste_button=apply,
                    tabname="txt2img" if not is_img2img else "img2img",
                    source_text_component=generation_info
                ))
                refresh = gr.Button('\U0001f504', scale=1)

            gallery = gr.Gallery(
                value=get_gallery_images(self.num_img, is_img2img),
                show_label=False,
                columns=self.num_cols,
                rows=self.num_rows,
                object_fit='contain',
                allow_preview=False,
                format='png',
            )

            gallery.select(
                fn=update_params,
                inputs=gallery,
                outputs=generation_info
            )
            refresh.click(lambda: get_gallery_images(self.num_img, is_img2img), outputs=gallery)
