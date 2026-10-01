import { useState } from 'react'
import { Routes, Route } from "react-router-dom"

import { MLB_Page } from './Pages/MLB.jsx'
import {PublicPage } from './Pages/PublicPage'

function App() {

  return (
    <Routes>
      <Route path="/" element={<PublicPage/>}/>
      <Route path="/MLB" element={<MLB_Page/>}/>
    </Routes>
  )
}

export default App
