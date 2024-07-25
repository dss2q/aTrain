from .models import stop_all_downloads
from multiprocessing import Process
from flask import Request
from werkzeug.datastructures import FileStorage
from io import BytesIO
from aTrain_core.GUI_integration import EventSender
from aTrain_core.check_inputs import check_inputs_transcribe
from aTrain_core.globals import TIMESTAMP_FORMAT
from aTrain_core.transcribe import transcribe
from aTrain_core.outputs import create_file_id
from datetime import datetime
import traceback

RUNNING_TRANSCRIPTIONS = []
EVENT_SENDER = EventSender()


def start_process(request: Request) -> None:
    """This function executes the transcription in a seperate process."""
    settings, file = get_inputs(request=request)
    transciption = Process(target=try_to_transcribe,
                           args=(settings, file.filename, file.stream.read(), EVENT_SENDER), daemon=True)
    transciption.start()
    RUNNING_TRANSCRIPTIONS.append(transciption)


def get_inputs(request: Request) -> tuple[dict, FileStorage]:
    """This function extracts the file and form data from the flask request and returns them."""
    file = request.files["file"]
    settings = dict(request.form)
    settings = resolve_boolean_inputs(settings)
    return settings, file


def resolve_boolean_inputs(settings: dict) -> dict:
    """This function checks if boolean inputs are present and replaces them with their respective values."""
    settings["speaker_detection"] = True if "speaker_detection" in settings else False
    settings["device"] = "GPU" if 'GPU' in settings else "CPU"
    settings["compute_type"] = "float16" if 'float16' in settings else "int8"
    return settings


def try_to_transcribe(settings: dict, file_name: str, file_content: bytes,  event_sender: EventSender) -> None:
    """A function that calls aTrain_core and handles errors if they happen."""
    try:
        start_transcription(settings, file_name, file_content,  event_sender)
    except Exception as error:
        traceback_str = traceback.format_exc()
        event_sender.error_info(str(error), traceback_str)


def start_transcription(settings: dict, file_name: str, file_content: bytes,  event_sender: EventSender) -> None:
    """A function that checks the inputs for the transcription and then transcribes the audio file."""
    check_inputs_transcribe(
        file=file_name, model=settings["model"], language=settings["language"], device=settings["device"])
    timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
    file_id = create_file_id(file_name, timestamp)
    transcribe(BytesIO(file_content), file_id, settings["model"], settings["language"], settings["speaker_detection"],
               settings["num_speakers"], settings["device"], settings["compute_type"], timestamp, event_sender)


def stop_all_transcriptions() -> None:
    """A function that terminates all running transcription processes."""
    process: Process
    for process in RUNNING_TRANSCRIPTIONS:
        process.terminate()
    RUNNING_TRANSCRIPTIONS.clear()


def teardown() -> None:
    """A function that is invoked when the application window closes and which terminates all processes that are still running."""
    EVENT_SENDER.end_stream()
    stop_all_transcriptions()
    stop_all_downloads()
