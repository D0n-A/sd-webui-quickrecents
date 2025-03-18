import modules.infotext_utils as parameters_copypaste
from modules import shared, shared_items, errors, ui_components
import modules.scripts as scripts
from functools import lru_cache
from heapq import nlargest
from pathlib import Path
from PIL import Image
import gradio as gr
import os
import re

allowed_ext = ('.png', '.jpg', '.jpeg', '.webp', '.avif')
allowed_dir_setting_keys = ['outdir_img2img_samples', 'outdir_txt2img_samples', 'outdir_samples', 'outdir_img2img_grids', 'outdir_txt2img_grids', 'outdir_grids']

shared.options_templates.update(shared.options_section(('quick_recent', 'Quick Recents'), {
    'quick_recent_include_grids': shared.OptionInfo(False, 'Include grid outputs in quick recent',gr.Checkbox),
    'quick_recent_total_recent_img': shared.OptionInfo(
        12, 'Total number of images to show in quick recent gallery',
        gr.Number, {'minimum': 1, 'maximum': 1000, 'precision': 0}
    ),
    'quick_recent_img_min_width': shared.OptionInfo(
        '12rem', 'Gallery Image minimum width', gr.Textbox,
    ).info("<a href='https://developer.mozilla.org/en-US/docs/Learn/CSS/Building_blocks/Values_and_units#lengths' target='_blank'>Accepts CSS length units.</a> Examples: '160px', '8vw', '10rem' (default)").needs_reload_ui(),
    'quick_recent_skip_pasting': shared.OptionInfo([], 'Parameter fields to disregard when applying quick recent', ui_components.DropdownMulti, lambda: {'choices': shared_items.get_infotext_names() + ['Sampler', 'Schedule type', 'Size']}),
}))

# set the default value min width gallery grid to --quick-recent-img-min-width CSS root variable
shared.gradio_theme.quick_recent_img_min_width = shared.opts.quick_recent_img_min_width

@lru_cache(maxsize=2048)
def create_fake_image(img_path):
    # create a fake image of 1x1 to send to gradio
    # Image.already_saved_as is a custom attribute of Webui to prevent gradio temp file creation
    fake_image = Image.new(mode='RGB', size=(1, 1))
    fake_image.already_saved_as = img_path
    return fake_image


def scan_images(dir_path):
    for root, _, fns in os.walk(dir_path):
        for fn in fns:
            if fn.lower().endswith(allowed_ext):
                yield os.path.join(root, fn)


def get_recent_images(n, is_img2img):
    # Crawl through txt/img2img directories to find recent images
    # if specified webui will output to outdir_samples first before using txt/img2img's own directories
    img_dir = shared.opts.outdir_samples or (shared.opts.outdir_img2img_samples if is_img2img else shared.opts.outdir_txt2img_samples)
    all_images = list(scan_images(img_dir))
    
    if shared.opts.quick_recent_include_grids:
        grid_dir = shared.opts.outdir_grids or (shared.opts.outdir_img2img_grids if is_img2img else shared.opts.outdir_txt2img_grids)
        all_images.extend(scan_images(grid_dir))
    
    return nlargest(int(n), all_images, key=os.path.getmtime)


def get_gallery_images(is_img2img):
    return [create_fake_image(img_path) for img_path in get_recent_images(shared.opts.quick_recent_total_recent_img, is_img2img)]


def test_allowed_dir(path: Path):
    path = path.resolve()
    for k in allowed_dir_setting_keys:
        parent = getattr(shared.opts, k).strip()
        if parent:
            parent = Path(parent).resolve()
            if path.is_relative_to(parent):
                return True
    return False


def update_params(image):
    # index of the image in the gallery from evt
    # images is the list of images in the gallery from the webpage
    # image_path contains separator '?', needs to be removed
    try:
        # Retrieve the selected options for skipping parameters
        skip_params = shared.opts.quick_recent_skip_pasting
        
        if isinstance(image, list):
            image = image[0][0]
        image, q, timestamp = image.rpartition('?')
        image_path = Path(image if q else timestamp)
        assert image_path.is_file(), f'File not found: {image_path}'
        assert test_allowed_dir(image_path), f'File not in allowed directories: {image_path}'
        with Image.open(image_path) as img:
            parameters = img.info.get('parameters', '')
            if 'Prompt' in skip_params:
                # Prompts are formatted differently so this looks for its endpoint (Steps/Negative Prompt) then deletes above it
                parameters = re.sub(r'^.*?(?=\b(Steps|Negative Prompt):)', '', parameters, flags=re.DOTALL)
            for param in skip_params:
                parameters = parameters.replace(f'{param}:', '')
            return parameters
    except Exception:
        errors.report('Error reading image parameters', exc_info=True)
    return ''


class QuickRecentsScript(scripts.Script):
    # So the tab appears at the top
    sorting_priority = -5

    def __init__(self):
        super().__init__()
        self.recent_images = []
        self.num_img = shared.opts.quick_recent_total_recent_img

    def title(self):
        return 'Quick Recents'

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def ui(self, is_img2img):
        with gr.Blocks(analytics_enabled=False) as block:
            generation_info = gr.Textbox(visible=False)

            with gr.Accordion('Quick Recents', open=False):
                with gr.Row():
                    apply = gr.Button('Apply', scale=19)
                    parameters_copypaste.register_paste_params_button(parameters_copypaste.ParamBinding(
                        paste_button=apply,
                        tabname='txt2img' if not is_img2img else 'img2img',
                        source_text_component=generation_info
                    ))
                    refresh = gr.Button('\U0001f504', scale=1)

                gallery = gr.Gallery(
                    value=None,
                    show_label=False,
                    object_fit='contain',
                    allow_preview=False,
                    interactive=False,
                    elem_id=self.elem_id('quick_recent_gallery'),
                    elem_classes=['quick-recent-gallery'],
                )

                gallery.select(
                    fn=update_params,
                    _js=f'(images) => get_quick_recent_gallery_selected_index("{self.elem_id("quick_recent_gallery")}", images)',
                    inputs=[
                        gallery
                    ],
                    outputs=generation_info,

                )
                refresh.click(lambda: get_gallery_images(is_img2img), outputs=[gallery])
                block.load(lambda: get_gallery_images(is_img2img), outputs=[gallery])
