from pathlib import Path
p = Path("LogicAnalyzer.c")
s = p.read_text()
# Only modification: re-arm the SAME original capture after its data is sent.
# No changes to capture engine, pins, sampling, triggers, or binary USB output.
needle = "CAPTURE_REQUEST* req;"
assert s.count(needle) == 1
s = s.replace(needle, needle + r'''

// Saved original host request for automatic re-arm after each completed capture.
static CAPTURE_REQUEST repeatCaptureRequest;
static bool repeatCaptureValid = false;

static bool repeatLastCapture(void)
{
    const CAPTURE_REQUEST *r = &repeatCaptureRequest;
    if (!repeatCaptureValid) return false;
    if (r->triggerType == 3)
        return StartCaptureBlast(r->frequency, r->postSamples, r->channels,
                                 r->channelCount, r->trigger, r->inverted,
                                 r->captureMode);
#ifdef SUPPORTS_COMPLEX_TRIGGER
    if (r->triggerType == 1)
        return StartCaptureComplex(r->frequency, r->preSamples, r->postSamples,
                                   r->channels, r->channelCount, r->trigger,
                                   r->count, r->triggerValue, r->captureMode);
    if (r->triggerType == 2)
        return StartCaptureFast(r->frequency, r->preSamples, r->postSamples,
                                r->channels, r->channelCount, r->trigger,
                                r->count, r->triggerValue, r->captureMode);
#else
    if (r->triggerType == 1 || r->triggerType == 2) return false;
#endif
    return StartCaptureSimple(r->frequency, r->preSamples, r->postSamples,
                              r->loopCount, r->measure, r->channels,
                              r->channelCount, r->trigger, r->inverted,
                              r->captureMode);
}
''')
needle = '                            capturing = true;'
assert s.count(needle) == 1
s = s.replace(needle, needle + '''
                            // Preserve exact original capture settings for the next run.
                            memcpy(&repeatCaptureRequest, req, sizeof(repeatCaptureRequest));
                            repeatCaptureValid = true;''')
needle = '                //Done!\n                capturing = false;'
assert s.count(needle) == 1
s = s.replace(needle, '''                //Done!
                capturing = false;
                // Re-arm only AFTER original binary USB transfer has completed.
                if (repeatCaptureValid)
                    capturing = repeatLastCapture();''')
p.write_text(s)
print("Applied continuous re-arm only; original output and capture engine intact.")
