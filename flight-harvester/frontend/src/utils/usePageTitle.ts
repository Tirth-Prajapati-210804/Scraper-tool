import { useEffect } from "react";

export function usePageTitle(title: string) {
  useEffect(() => {
    document.title = title ? `${title} — Flight Harvester` : "Flight Harvester";
    return () => {
      document.title = "Flight Harvester";
    };
  }, [title]);
}
