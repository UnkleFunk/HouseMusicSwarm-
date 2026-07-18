def __getattr__(name):
    if name == "ListAudioDevices":
        from .ListAudioDevices import ListAudioDevices
        return ListAudioDevices
    if name == "CaptureAudio":
        from .CaptureAudio import CaptureAudio
        return CaptureAudio
    if name == "ExtractFeatures":
        from .ExtractFeatures import ExtractFeatures
        return ExtractFeatures
    if name == "BuildDatabase":
        from .BuildDatabase import BuildDatabase
        return BuildDatabase
    if name == "SearchReferences":
        from .SearchReferences import SearchReferences
        return SearchReferences
    if name == "FormatResults":
        from .FormatResults import FormatResults
        return FormatResults
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "ListAudioDevices",
    "CaptureAudio",
    "ExtractFeatures",
    "BuildDatabase",
    "SearchReferences",
    "FormatResults",
]
