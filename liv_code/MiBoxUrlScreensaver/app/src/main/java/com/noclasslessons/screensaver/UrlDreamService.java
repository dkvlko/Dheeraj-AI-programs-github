package com.noclasslessons.screensaver;

import android.annotation.SuppressLint;
import android.graphics.Color;
import android.os.Bundle;
import android.service.dreams.DreamService;
import android.view.View;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class UrlDreamService extends DreamService {

    private static final String URL =
            "https://app.noclasslessons.com:8000/clock_lap/";

    private WebView webView;

    @Override
    public void onAttachedToWindow() {
        super.onAttachedToWindow();

        setInteractive(false);
        setFullscreen(true);
        setScreenBright(false);

        createWebView();
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void createWebView() {

        webView = new WebView(this);

        webView.setBackgroundColor(Color.BLACK);

        WebSettings settings = webView.getSettings();

        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);

        settings.setLoadWithOverviewMode(false);
        settings.setUseWideViewPort(true);

        settings.setMediaPlaybackRequiresUserGesture(false);

        webView.setWebViewClient(new WebViewClient());

        webView.setWebChromeClient(new WebChromeClient());

        setContentView(webView);

        webView.loadUrl(URL);
    }

    @Override
    public void onDreamingStarted() {
        super.onDreamingStarted();

        if (webView != null) {
            webView.loadUrl(URL);
        }
    }

    @Override
    public void onDreamingStopped() {
        super.onDreamingStopped();

        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
            webView = null;
        }
    }

    @Override
    public void onDetachedFromWindow() {

        if (webView != null) {
            webView.destroy();
            webView = null;
        }

        super.onDetachedFromWindow();
    }
}
