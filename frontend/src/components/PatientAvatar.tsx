// Stable per-patient colour so every avatar has its own identity — warmth
// without a photo (tester feedback: too clinical). Full static classes for
// Tailwind. A photo, when present, wins; initials are the fallback.
const PALETTE = [
  "bg-violet-400 dark:bg-violet-500",
  "bg-sky-400 dark:bg-sky-500",
  "bg-emerald-400 dark:bg-emerald-500",
  "bg-amber-400 dark:bg-amber-500",
  "bg-rose-400 dark:bg-rose-500",
  "bg-teal-400 dark:bg-teal-500",
  "bg-orange-400 dark:bg-orange-500",
  "bg-indigo-400 dark:bg-indigo-500",
];

function colorFor(seed: string): string {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

export function PatientAvatar({
  givenName,
  familyName,
  photoUrl,
  className = "size-20 text-2xl",
}: {
  givenName?: string;
  familyName?: string;
  photoUrl?: string | null;
  className?: string;
}) {
  const initials = `${givenName?.[0] ?? "?"}${familyName?.[0] ?? ""}`.toUpperCase();
  const color = colorFor(`${givenName ?? ""} ${familyName ?? ""}`);
  return (
    <div className="relative shrink-0">
      <div className={`flex items-center justify-center rounded-full font-semibold text-white overflow-hidden ${photoUrl ? "" : color} ${className}`}>
        {photoUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={photoUrl} alt="" className="h-full w-full object-cover" />
        ) : (
          <span>{initials}</span>
        )}
      </div>
    </div>
  );
}
