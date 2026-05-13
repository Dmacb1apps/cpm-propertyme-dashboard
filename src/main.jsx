import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import CPMDashboard from "./CPMDashboard.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <CPMDashboard />
  </StrictMode>
);
