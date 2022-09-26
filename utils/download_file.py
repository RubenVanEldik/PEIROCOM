from datetime import datetime
import py7zr
import requests
import streamlit as st

import utils
import validate


def download_file(url, filename, *, unzip=False, chunk_size=50 * 1024, show_progress=False):
    """
    Download the file from a specific URL and unzip if requested
    """
    assert validate.is_url(url)
    assert validate.is_filepath(filename) or validate.is_directory_path(filename)
    assert validate.is_bool(unzip)
    assert validate.is_integer(chunk_size)
    assert validate.is_bool(show_progress)

    # Create a temporary filename for if it needs to be unzipped
    filename_zip = utils.path(f"temp_{datetime.now().timestamp()}.zip")

    # Create the request
    r = requests.get(url, stream=True)

    # Show an error and return the function if the status code is not 200
    if r.status_code != 200:
        st.error(f"Error requesting {url}")
        return

    # Create the file and start downloading
    with open(filename_zip if unzip else filename, "wb") as f:
        size_total = int(r.headers["Content-length"])
        size_downloaded = 0

        # Create the progress_bar if required
        if show_progress:
            progress_bar = st.progress(0.0)

        # Download the file in chunks
        for chunk in r.iter_content(chunk_size=chunk_size):
            size_downloaded += chunk_size

            # Update the progress_bar
            if show_progress:
                progress_bar.progress(min(1.0, size_downloaded / size_total))

            # Write the new chunk to the file
            if chunk:
                f.write(chunk)

        # Remove the progress bar when the file has been downloaded
        progress_bar.empty()

    # Unzip the file and remove the ZIP file
    if unzip:
        with st.spinner("Unzipping files..."):
            with py7zr.SevenZipFile(filename_zip, mode="r") as f:
                f.extractall(filename)
        filename_zip.unlink()
