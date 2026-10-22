// The Night session's sky (the "Àlọ́ Night Session V" design): twinkling
// stars, two drifting aurora washes, rain over the listening story and
// a vignette. All decorative and hidden from assistive tech. Motion is
// CSS transform and opacity only (see session.css), and is switched off
// under prefers-reduced-motion, leaving the stars still.
export default function Atmosphere({ rain = false }: { rain?: boolean }) {
  return (
    <div className={`night-atmosphere${rain ? ' night-atmosphere--rain' : ''}`} aria-hidden="true">
      <span className="night-aurora night-aurora--a" />
      <span className="night-aurora night-aurora--b" />
      <span className="night-stars night-stars--a" />
      <span className="night-stars night-stars--b" />
      {rain ? <span className="night-rain" /> : null}
      <span className="night-vignette" />
    </div>
  );
}
