import apiClient from './apiClient';

export interface UserAdminDTO {
  id: string;
  fullName: string;
  email: string;
  role: string;
  status: string;
  avatarUrl: string;
  postCount: number;
}

export interface ListingAdminDTO {
  id: string;
  title: string;
  price: number;
  area: number;
  address: string;
  ownerName: string;
  status: string;
  createdAt: string;
  imageUrl: string;
}

export interface StatisticsDTO {
  totalUsers: number;
  pendingListings: number;
  totalListings: number;
  totalViews: number;
}

export const adminService = {
  getAllUsers: async (): Promise<UserAdminDTO[]> => {
    const response = await apiClient.get('/admin/users');
    return response.data;
  },

  getAllListings: async (): Promise<ListingAdminDTO[]> => {
    const response = await apiClient.get('/admin/listings');
    return response.data;
  },

  getStatistics: async (): Promise<StatisticsDTO> => {
    const response = await apiClient.get('/admin/statistics');
    return response.data;
  },

  changeUserStatus: async (userId: string, status: string): Promise<any> => {
    const response = await apiClient.patch(`/admin/users/${userId}/status`, { status });
    return response.data;
  },

  changeListingStatus: async (listingId: string, status: string): Promise<any> => {
    const response = await apiClient.patch(`/admin/listings/${listingId}/status`, { status });
    return response.data;
  }
};
