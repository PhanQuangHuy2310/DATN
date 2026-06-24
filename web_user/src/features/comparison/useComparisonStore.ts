import { create } from 'zustand';

interface ComparisonState {
  selectedListingIds: string[];
  addListing: (id: string) => void;
  removeListing: (id: string) => void;
  clear: () => void;
  isOpen: boolean;
  setIsOpen: (isOpen: boolean) => void;
}

export const useComparisonStore = create<ComparisonState>((set) => ({
  selectedListingIds: [],
  addListing: (id) =>
    set((state) => {
      if (state.selectedListingIds.length >= 3 || state.selectedListingIds.includes(id)) {
        return state; // Tối đa 3 phòng
      }
      return { selectedListingIds: [...state.selectedListingIds, id] };
    }),
  removeListing: (id) =>
    set((state) => ({
      selectedListingIds: state.selectedListingIds.filter((item) => item !== id),
    })),
  clear: () => set({ selectedListingIds: [] }),
  isOpen: false,
  setIsOpen: (isOpen) => set({ isOpen }),
}));
