import { Routes, Route } from "react-router-dom";
import { RootLayout, BareLayout } from "./layouts";
import { ProtectedRoute } from "./ProtectedRoute";

import { HomePage } from "@/pages/home";
import { SearchPage } from "@/pages/search";
import { ListingDetailPage } from "@/pages/listing-detail";
import { CreateListingPage } from "@/pages/create-listing";
import { AppointmentsPage } from "@/pages/appointments";
import { ProfilePage } from "@/pages/profile";
import { ChatPage } from "@/pages/chat";
import { LandlordDashboardPage } from "@/pages/landlord-dashboard";
import { AuthPage } from "@/pages/auth";
import { PaymentCallbackPage } from "@/pages/payment-callback";
import { RoommatePage } from "@/pages/roommate";
import { NotFoundPage } from "@/pages/not-found";
import { ComparisonTray, ComparisonModal } from "@/features/comparison";

export function App() {
  return (
    <>
      <Routes>
      {/* Auth screens — standalone, no chrome */}
      <Route path="/login" element={<AuthPage />} />
      <Route path="/register" element={<AuthPage />} />

      {/* Full-height map / chat */}
      <Route element={<BareLayout />}>
        <Route path="/search" element={<SearchPage />} />
        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <ChatPage />
            </ProtectedRoute>
          }
        />
      </Route>

      {/* Standard content pages */}
      <Route element={<RootLayout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/listings/:id" element={<ListingDetailPage />} />
        <Route path="/roommates" element={<RoommatePage />} />
        <Route
          path="/listings/create"
          element={
            <ProtectedRoute>
              <CreateListingPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/listings/:id/edit"
          element={
            <ProtectedRoute>
              <CreateListingPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/appointments"
          element={
            <ProtectedRoute>
              <AppointmentsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <ProfilePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/landlord/dashboard"
          element={
            <ProtectedRoute roles={["LANDLORD"]}>
              <LandlordDashboardPage />
            </ProtectedRoute>
          }
        />
        <Route path="/payment/callback" element={<PaymentCallbackPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
      <ComparisonTray />
      <ComparisonModal />
    </>
  );
}
