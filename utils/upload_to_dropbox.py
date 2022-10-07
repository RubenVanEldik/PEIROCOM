import dropbox

import utils
import validate

# Initialize the Dropbox client
dropbox_app_key = utils.getenv("DROPBOX_APP_KEY")
dropbox_app_secret = utils.getenv("DROPBOX_APP_SECRET")
dropbox_refresh_token = utils.getenv("DROPBOX_REFRESH_TOKEN")
if dropbox_app_key and dropbox_app_secret and dropbox_refresh_token:
    client = dropbox.Dropbox(app_key=dropbox_app_key, app_secret=dropbox_app_secret, oauth2_refresh_token=dropbox_refresh_token)


def _upload_file(filepath, dropbox_directory_path):
    """
    Upload a file to Dropbox
    """
    assert validate.is_filepath(filepath)
    assert validate.is_directory_path(dropbox_directory_path)

    file_size = filepath.stat().st_size
    chunk_size = 4 * 1024 * 1024

    with open(filepath, "rb") as f:
        upload_session_start_result = client.files_upload_session_start(f.read(chunk_size))
        cursor = dropbox.files.UploadSessionCursor(session_id=upload_session_start_result.session_id, offset=f.tell())
        commit = dropbox.files.CommitInfo(path=f"/{dropbox_directory_path / filepath.name}", mute=True)
        while f.tell() < file_size:
            if (file_size - f.tell()) <= chunk_size:
                client.files_upload_session_finish(f.read(chunk_size), cursor, commit)
            else:
                client.files_upload_session_append(f.read(chunk_size), cursor.session_id, cursor.offset)
                cursor.offset = f.tell()


def upload_to_dropbox(path, dropbox_directory_path):
    """
    Upload a file or directory to Dropbox
    """
    assert validate.is_directory_path(path) or validate.is_filepath(path)
    assert validate.is_directory_path(dropbox_directory_path)

    if "client" not in globals():
        print("Could not upload to Dropbox because DROPBOX_ACCESS_TOKEN was not set")
        return

    # If the path is a directory upload the files as a ZIP file
    if path.is_dir():
        utils.zip(path)
        _upload_file(path.parent / f"{path.name}.zip", dropbox_directory_path)
    else:
        _upload_file(path, dropbox_directory_path)
