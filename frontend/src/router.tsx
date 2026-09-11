import { createBrowserRouter, Navigate } from "react-router-dom";
import App from "./App";
import { ChatPage } from "./pages/ChatPage";
import { MapPage } from "./pages/MapPage";
import { ItineraryPage } from "./pages/ItineraryPage";
import { WishlistPage } from "./pages/WishlistPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Navigate to="/chat" replace /> },
      { path: "chat", element: <ChatPage /> },
      { path: "map", element: <MapPage /> },
      { path: "itinerary", element: <ItineraryPage /> },
      { path: "wishlist", element: <WishlistPage /> },
    ],
  },
]);
