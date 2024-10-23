function get_quick_recent_gallery_selected_index(gallery_id, images) {
    const galleryElement = document.getElementById(gallery_id);
    if (galleryElement) {
        const thumbnails = galleryElement.querySelectorAll('button.thumbnail-item');
        const index = Array.from(thumbnails).findIndex(button => button.classList.contains('selected'));
        if (index >= 0 && index < images.length) {
            let image_path = images[index].name;
            if (image_path === undefined) {
                return [[images[index]]]; // forge
            }
            return image_path; // a1111
        }
    }
    return '';
}