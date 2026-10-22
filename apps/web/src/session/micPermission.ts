// Asking for the microphone (B7). The browser's own prompt cannot be
// styled, so the app explains first and only then calls this. The probe
// stream is stopped straight away: it only finds out whether the child's
// phone will let Alo.ai listen. The real audio is published by the
// session driver once the session starts.
export type MicResult = 'granted' | 'denied' | 'unavailable';

export async function requestMic(
  media: Pick<MediaDevices, 'getUserMedia'> | undefined = typeof navigator === 'undefined'
    ? undefined
    : navigator.mediaDevices,
): Promise<MicResult> {
  if (!media || typeof media.getUserMedia !== 'function') return 'unavailable';
  try {
    const stream = await media.getUserMedia({ audio: true });
    stream.getTracks().forEach((track) => track.stop());
    return 'granted';
  } catch (error) {
    const name = (error as { name?: string } | null)?.name;
    // No microphone at all, or one that cannot be opened, is not the same as "blocked".
    if (name === 'NotFoundError' || name === 'NotReadableError' || name === 'OverconstrainedError') {
      return 'unavailable';
    }
    return 'denied';
  }
}
