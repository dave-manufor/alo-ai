// Asking for the microphone (B7). The browser's own prompt cannot be
// styled, so the app explains first and only then calls this.
//
// The stream that comes back is KEPT: it is the one the session publishes to the room and the
// one the level meter listens to. Opening the microphone, stopping it and opening it again for
// the room (what this did before) is a second getUserMedia that Safari can answer with a
// quieter or muted input, and the agent then hears nothing.
export type MicResult = 'granted' | 'denied' | 'unavailable';

// Echo cancellation stays on (Kemi's voice plays out of the same phone). Noise suppression is
// off: it can take a quiet child's voice for noise and leave the agent almost silence. Gain is
// automatic so a soft voice is lifted.
export const MIC_CONSTRAINTS: MediaTrackConstraints = {
  echoCancellation: true,
  noiseSuppression: false,
  autoGainControl: true,
  channelCount: 1,
};

export interface OpenedMic {
  result: MicResult;
  /** The live stream, when `result` is 'granted'. The caller owns it and stops it. */
  stream?: MediaStream;
}

export async function openMic(
  media: Pick<MediaDevices, 'getUserMedia'> | undefined = typeof navigator === 'undefined'
    ? undefined
    : navigator.mediaDevices,
): Promise<OpenedMic> {
  if (!media || typeof media.getUserMedia !== 'function') return { result: 'unavailable' };
  try {
    const stream = await media.getUserMedia({ audio: MIC_CONSTRAINTS });
    // What the browser actually applied, for working out a quiet microphone (no audio content).
    const settings = stream.getAudioTracks?.()[0]?.getSettings?.();
    if (settings) {
      console.info('microphone settings:', {
        echoCancellation: settings.echoCancellation,
        noiseSuppression: settings.noiseSuppression,
        autoGainControl: settings.autoGainControl,
        sampleRate: settings.sampleRate,
        channelCount: settings.channelCount,
      });
    }
    return { result: 'granted', stream };
  } catch (error) {
    const name = (error as { name?: string } | null)?.name;
    // No microphone at all, or one that cannot be opened, is not the same as "blocked".
    if (name === 'NotFoundError' || name === 'NotReadableError' || name === 'OverconstrainedError') {
      return { result: 'unavailable' };
    }
    return { result: 'denied' };
  }
}

export function stopMic(stream: MediaStream | null | undefined): void {
  stream?.getTracks().forEach((track) => track.stop());
}
