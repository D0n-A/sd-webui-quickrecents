import modules.scripts as scripts
import modules.infotext_utils as parameters_copypaste
import gradio as gr
import os
from heapq import nlargest
from pathlib import Path
from modules import shared
import shutil
import tempfile
from PIL import Image

class QuickRecentsScript(scripts.Script):
        # So the tap appears at the top
        sorting_priority = -5

        def title(self):
                return "Quick Recents"

        def show(self, is_img2img):
                return scripts.AlwaysVisible

        def ui(self, is_img2img):
                
                # Crawl through txt/img2img directories to find recent images
                def get_recent(n):
                        txt2img_dir = shared.opts.outdir_img2img_samples if is_img2img else shared.opts.outdir_txt2img_samples
                        png_files = (str(Path(root) / file) for root, _, files in os.walk(txt2img_dir) for file in files if file.endswith('.png'))
                        recent_files = nlargest(n, png_files, key=os.path.getmtime)
                        return recent_files
                
                # To avoid gradio caching issues
                def cache_files(file_paths):
                        cache_dir = tempfile.gettempdir()
                        cached_files = []
                        for file_path in file_paths:
                                dest_path = Path(cache_dir) / Path(file_path).name
                                shutil.copy(file_path, dest_path)
                                cached_files.append(str(dest_path))
                        return cached_files

                num_img = 8
                num_cols = 2
                num_rows = (num_img + num_cols - 1) // num_cols

                # Get Paraminfo of image through metadata
                def update_params(evt: gr.SelectData):
                        imgpat = evt.value['image']['path']
                        with Image.open(imgpat) as img:
                                metadata = img.info
                        geninfo = metadata.get("parameters")
                        return geninfo
                
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

                        gallery = gr.Gallery(value=cache_files(get_recent(num_img)), 
                                             show_label=False, 
                                             columns=num_cols, 
                                             rows=num_rows,
                                             object_fit='contain',
                                             allow_preview=False,
                                             format='png',
                                             )

                        gallery.select(update_params, outputs=generation_info)
                        refresh.click(lambda: cache_files(get_recent(num_img)), outputs=gallery)
