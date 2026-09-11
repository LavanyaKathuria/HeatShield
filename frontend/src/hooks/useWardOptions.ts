import { useEffect, useState } from 'react'
import { loadWardGeojson } from '@/lib/wardGeojson'

export interface WardOption {
  ward_id: string
  ward_name: string
}

export function useWardOptions() {
  const [wards, setWards] = useState<WardOption[]>([])

  useEffect(() => {
    loadWardGeojson().then((geojson) => {
      const options = geojson.features
        .map((f) => ({ ward_id: f.properties.sourcewardcode, ward_name: f.properties.sourcewardname }))
        .sort((a, b) => a.ward_name.localeCompare(b.ward_name))
      setWards(options)
    })
  }, [])

  return wards
}
