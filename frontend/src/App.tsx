import { Navigate, createBrowserRouter, RouterProvider } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ApprovalCenter } from "./pages/ApprovalCenter";
import { Dashboard } from "./pages/Dashboard";
import { DemoScenarios } from "./pages/DemoScenarios";
import { IncidentDetail } from "./pages/IncidentDetail";
import { IncidentList } from "./pages/IncidentList";
import { RpaRuns } from "./pages/RpaRuns";
import { WorkOrders } from "./pages/WorkOrders";

const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "incidents", element: <IncidentList /> },
      { path: "incidents/:id", element: <IncidentDetail /> },
      { path: "approvals", element: <ApprovalCenter /> },
      { path: "work-orders", element: <WorkOrders /> },
      { path: "rpa-runs", element: <RpaRuns /> },
      { path: "demo", element: <DemoScenarios /> },
      { path: "*", element: <Navigate to="/" replace /> }
    ]
  }
]);

export function App() {
  return <RouterProvider router={router} />;
}
