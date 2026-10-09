import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "OpenAvisio",
    short_name: "OpenAvisio",
    description: "The AI assistant for everyone who cares",
    start_url: "/",
    display: "standalone",
    // warm ivory --background (globals.css), the same as ThemeColorMeta
    background_color: "#f5f4ee",
    theme_color: "#f5f4ee",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      // without a maskable icon Android drops ours into a white circle instead
      // of masking it to the launcher's shape
      { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
