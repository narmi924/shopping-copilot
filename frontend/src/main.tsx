import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ConfigProvider } from "antd";
import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: "#0071e3",
          colorLink: "#0066cc",
          colorText: "#1d1d1f",
          colorTextSecondary: "#6e6e73",
          colorBgBase: "#ffffff",
          colorBorder: "rgba(0, 0, 0, 0.1)",
          borderRadius: 8,
          fontFamily: '"SF Pro Text", "SF Pro Icons", "Helvetica Neue", Helvetica, Arial, sans-serif',
          controlHeight: 44,
        },
        components: {
          Button: { borderRadius: 980, primaryShadow: "none" },
          Input: { activeShadow: "0 0 0 2px rgba(0, 113, 227, 0.12)" },
          Modal: { borderRadiusLG: 12 },
          Tag: { borderRadiusSM: 980 },
        },
      }}
    >
      <App />
    </ConfigProvider>
  </StrictMode>,
);
