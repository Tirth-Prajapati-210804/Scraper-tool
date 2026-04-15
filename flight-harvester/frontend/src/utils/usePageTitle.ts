import { useEffect } from "react";

export function usePageTitle(title: string) {
  useEffect(() => {
    document.title = title ? `${title} — Flight Data Scrapper` : "Flight Data Scrapper";
    return () => {
      document.title = "Flight Data Scrapper";
    };
  }, [title]);
}
