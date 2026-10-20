import { getTranslations } from "next-intl/server";

// Server actions hand their error text straight to the UI, so it is translated here (#372).
export async function actionError(key: string, values?: Record<string, string | number>) {
  return (await getTranslations())(key, values);
}
