import dropbox

import utils
import validate

# Initialize the Dropbox client
dropbox_app_key = utils.getenv("DROPBOX_APP_KEY")
dropbox_app_secret = utils.getenv("DROPBOX_APP_SECRET")
dropbox_refresh_token = utils.getenv("DROPBOX_REFRESH_TOKEN")
if dropbox_app_key and dropbox_app_secret and dropbox_refresh_token:
    client = dropbox.Dropbox(app_key=dropbox_app_key, app_secret=dropbox_app_secret, oauth2_refresh_token=dropbox_refresh_token)


def upload_to_dropbox(path, dropbox_path):
    """
    Upload a file or directory to Dropbox
    """
    assert validate.is_directory_path(path) or validate.is_filepath(path)
    assert validate.is_directory_path(dropbox_path)

    if "client" not in globals():
        print("Could not upload to Dropbox because DROPBOX_ACCESS_TOKEN was not set")
        return

    # If the path is a directory upload the files as a ZIP file
    if path.is_dir():
        utils.zip(path)
        client.files_upload(open(f"{path}.zip", "rb").read(), f"/{dropbox_path / path.name}.zip", mute=True)
    else:
        client.files_upload(open(path, "rb").read(), f"/{dropbox_path / path.name}", mute=True)
