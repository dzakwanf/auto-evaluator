import { AppProps } from "next/app";
import Head from "next/head";
import { MantineProvider, MantineThemeOverride } from "@mantine/core";
import React from "react";
import { IS_DEV } from "../utils/variables";
import * as snippet from "@segment/snippet";
import { useEffect } from "react";
import { Notifications } from "@mantine/notifications";
import { Analytics } from "@vercel/analytics/react";
import LogRocket from "logrocket";
import * as Sentry from "@sentry/browser";

if (!IS_DEV) {
  Sentry.init({
    dsn: "https://065aa152c4de4e14af9f9e7335c8eae4@o4505106202820608.ingest.sentry.io/4505106207735808",
    release: "evaluator@1.0.0",
    integrations: [new Sentry.BrowserTracing()],
    tracesSampleRate: 1.0,
  });

  LogRocket.init("dyuioj/auto-evaluator");

  LogRocket.getSessionURL((sessionURL) => {
    Sentry.configureScope((scope) => {
      scope.setExtra("sessionURL", sessionURL);
    });
  });
}

const renderSegmentSnippet = () => {
  const opts = {
    apiKey: process.env.NEXT_PUBLIC_SEGMENT_KEY,
    page: true,
  };

  return snippet.min(opts);
};

export default function App(props: AppProps) {
  const { Component, pageProps } = props;
  const theme: MantineThemeOverride = {
    primaryColor: "dark",
    fontFamily:
      "Greycliff CF, Inter,-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue,Arial, Noto Sans",
  };
  const pageName = "Dzakwan Evaluator";
  useEffect(() => {
    if (!IS_DEV) {
      // @ts-expect-error
      global.window.analytics.page();
    }
  }, [props]);
  return (
    <>
      <Head>
        <link rel="icon" href="favicon/favicon.ico" />
        <link rel="icon" sizes="32x32" href="favicon/favicon-32x32.png" />
        <link rel="icon" sizes="16x16" href="favicon/favicon-16x16.png" />
        <link
          rel="apple-touch-icon"
          sizes="180x180"
          href="/apple-touch-icon.png"
        />

        <link rel="icon" href="favicon/favicon.ico" />
        <link rel="icon" href="favicon/favicon.ico" />
        <meta
          name="description"
          content="Auto-Evaluator helps you evaluate your LLM apps."
        />
        <meta name="og:title" content={pageName} />
        <meta name="twitter:card" content="summary_large_image" />
        <title>{pageName}</title>
        {!IS_DEV && (
          <>
            <script
              // eslint-disable-next-line react/no-danger
              dangerouslySetInnerHTML={{ __html: renderSegmentSnippet() }}
            />
          </>
        )}
      </Head>
      <MantineProvider
        withGlobalStyles
        withNormalizeCSS
        theme={{
          /** Put your mantine theme override here */
          colorScheme: "light",
          ...theme,
        }}
      >
        <Notifications />
        <Component {...pageProps} />
        <Analytics />
      </MantineProvider>
    </>
  );
}
