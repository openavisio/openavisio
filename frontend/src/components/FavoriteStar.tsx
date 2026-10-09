"use client";

import { useState, useTransition } from "react";
import { Star } from "lucide-react";
import { useRouter } from "next/navigation";
import { addFavorite, removeFavorite } from "@/lib/api";

export function FavoriteStar({
  patientId,
  initial,
  className = "",
}: {
  patientId: string;
  initial: boolean;
  className?: string;
}) {
  const [fav, setFav] = useState(initial);
  const [pending, startTransition] = useTransition();
  const router = useRouter();

  function toggle(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    const next = !fav;
    setFav(next); // optimistic
    startTransition(async () => {
      try {
        await (next ? addFavorite(patientId) : removeFavorite(patientId));
        router.refresh(); // update sidebar + list sections
      } catch {
        setFav(!next); // revert
      }
    });
  }

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={pending}
      aria-pressed={fav}
      aria-label={fav ? "Unfavorite" : "Favorite"}
      className={`shrink-0 rounded p-1 transition-colors disabled:opacity-50 ${
        fav ? "text-amber-500 hover:text-amber-600" : "text-muted-foreground/40 hover:text-amber-500"
      } ${className}`}
    >
      <Star className="size-5" fill={fav ? "currentColor" : "none"} />
    </button>
  );
}
