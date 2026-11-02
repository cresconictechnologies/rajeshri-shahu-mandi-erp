package com.rajeshri.mandierp.inspector;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

public class ServerSettingsActivity extends AppCompatActivity {

    private static final String PREFS_NAME = "MandiQCPrefs";
    private static final String KEY_SERVER_URL = "server_url";
    private static final String DEFAULT_URL = "https://mandi-erp-tracker.vercel.app/app";

    private EditText etServerUrl;
    private Button btnSaveServer;
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_settings);

        prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);

        etServerUrl = findViewById(R.id.etServerUrl);
        btnSaveServer = findViewById(R.id.btnSaveServer);

        String currentUrl = prefs.getString(KEY_SERVER_URL, DEFAULT_URL);
        etServerUrl.setText(currentUrl);

        btnSaveServer.setOnClickListener(v -> {
            String inputUrl = etServerUrl.getText().toString().trim();
            if (inputUrl.isEmpty()) {
                Toast.makeText(this, "Please enter a valid server URL", Toast.LENGTH_SHORT).show();
                return;
            }
            if (!inputUrl.startsWith("http://") && !inputUrl.startsWith("https://")) {
                inputUrl = "http://" + inputUrl;
            }
            if (!inputUrl.contains("/inspector")) {
                if (inputUrl.endsWith("/")) {
                    inputUrl += "inspector/portal";
                } else {
                    inputUrl += "/inspector/portal";
                }
            }

            prefs.edit().putString(KEY_SERVER_URL, inputUrl).apply();
            Toast.makeText(this, "Yard Server URL Updated!", Toast.LENGTH_SHORT).show();
            finish();
        });
    }
}
