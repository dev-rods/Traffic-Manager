import { createBrowserRouter } from 'react-router-dom'
import { BookingLayout } from '@/layouts/BookingLayout'
import { Home } from '@/pages/Home'
import { Booking } from '@/pages/Booking'
import { NotFound } from '@/pages/NotFound'

export const router = createBrowserRouter([
  {
    path: '/:clinicId',
    element: <BookingLayout />,
    children: [
      { index: true, element: <Home /> },
      { path: 'agendar', element: <Booking /> },
    ],
  },
  { path: '*', element: <NotFound /> },
])
