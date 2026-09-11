import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import '@/i18n'
import '@/index.css'
import App from '@/App'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: 1,
      // The forecast doesn't change second-to-second - refetching every
      // time the browser tab regains focus just repaints the map and
      // panel for no new data, which reads as an unwanted "reload."
      // The 5-minute refetchInterval already on these queries (see
      // useForecastData.ts) is what keeps them current.
      refetchOnWindowFocus: false,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>
)
