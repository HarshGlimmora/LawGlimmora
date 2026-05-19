"use client";

import { useQuery } from "@tanstack/react-query";

import { authEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";

export function useSession() {
  return useQuery({
    queryKey: qk.me,
    queryFn: authEndpoints.me,
    retry: false,
    staleTime: 60_000,
  });
}
