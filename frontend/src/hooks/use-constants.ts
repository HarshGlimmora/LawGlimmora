"use client";

import { useQuery } from "@tanstack/react-query";

import { constantsEndpoint } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";

export function useConstants() {
  return useQuery({
    queryKey: qk.constants,
    queryFn: constantsEndpoint,
    staleTime: Infinity,
  });
}
