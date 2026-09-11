// TypeScript port of src/weather/heat_stress.py, for the "Thermometer vs
// Reality" widget's live what-if humidity slider - it needs instant
// recompute on every drag tick, which a backend round-trip can't give.
// Same formulas, same coefficients, same citations as the Python
// version (Rothfusz 1990 for HI, Australian BOM for WBGT-shade, Broede
// et al. 2012 for UTCI) - kept in sync by hand since there's no shared
// codegen between the Python backend and this frontend.

const STEFAN_BOLTZMANN = 5.670374419e-8
const PROJECTED_AREA_FACTOR = 0.25
const BODY_EMISSIVITY = 0.97

const UTCI_MIN_WIND_MS = 0.5
const UTCI_MAX_WIND_MS = 17.0

const UTCI_STRESS_CATEGORIES: [number, string][] = [
  [-40.0, 'extreme cold stress'],
  [-27.0, 'very strong cold stress'],
  [-13.0, 'strong cold stress'],
  [0.0, 'moderate cold stress'],
  [9.0, 'slight cold stress'],
  [26.0, 'no thermal stress'],
  [32.0, 'moderate heat stress'],
  [38.0, 'strong heat stress'],
  [46.0, 'very strong heat stress'],
]

export function estimateMeanRadiantTemperature(tempC: number, solarRadiationWm2: number): number {
  const tempK = tempC + 273.15
  const radiantLoad =
    (PROJECTED_AREA_FACTOR * Math.max(solarRadiationWm2, 0)) / (BODY_EMISSIVITY * STEFAN_BOLTZMANN)
  const mrtK = Math.pow(Math.pow(tempK, 4) + radiantLoad, 0.25)
  return mrtK - 273.15
}

export function calculateWbgtShade(tempC: number, relativeHumidity: number): number {
  const vapourPressure = (relativeHumidity / 100) * 6.105 * Math.exp((17.27 * tempC) / (237.7 + tempC))
  return 0.567 * tempC + 0.393 * vapourPressure + 3.94
}

export function calculateHeatIndex(tempC: number, relativeHumidity: number): number | null {
  if (tempC < 27) return null
  const t = tempC
  const rh = relativeHumidity
  return (
    -8.784695 +
    1.61139411 * t +
    2.338549 * rh -
    0.14611605 * t * rh -
    1.2308094e-2 * t ** 2 -
    1.6424828e-2 * rh ** 2 +
    2.211732e-3 * t ** 2 * rh +
    7.2546e-4 * t * rh ** 2 -
    3.582e-6 * t ** 2 * rh ** 2
  )
}

function saturationVapourPressureHpa(tempC: number): number {
  const g = [-2836.5744, -6028.076559, 19.54263612, -0.02737830188, 0.000016261698, 7.0229056e-10, -1.8680009e-13]
  const tempK = tempC + 273.15
  let logEs = 2.7150305 * Math.log1p(tempK)
  g.forEach((coefficient, power) => {
    logEs += coefficient * Math.pow(tempK, power - 2)
  })
  return Math.exp(logEs) * 0.01
}

// Broede et al. (2012) polynomial - same coefficients as
// src/weather/heat_stress.py::_utci_polynomial. Verified byte-for-byte
// against that implementation for a range of inputs before shipping.
function utciPolynomial(tdb: number, v: number, dTr: number, pa: number): number {
  const t = tdb,
    d = dTr,
    p = pa
  return (
    t +
    0.607562052 +
    -0.0227712343 * t +
    8.06470249e-4 * t * t +
    -1.54271372e-4 * t ** 3 +
    -3.24651735e-6 * t ** 4 +
    7.32602852e-8 * t ** 5 +
    1.35959073e-9 * t ** 6 +
    -2.2583652 * v +
    0.0880326035 * t * v +
    0.00216844454 * t * t * v +
    -1.53347087e-5 * t ** 3 * v +
    -5.72983704e-7 * t ** 4 * v +
    -2.55090145e-9 * t ** 5 * v +
    -0.751269505 * v * v +
    -0.00408350271 * t * v * v +
    -5.21670675e-5 * t * t * v * v +
    1.94544667e-6 * t ** 3 * v * v +
    1.14099531e-8 * t ** 4 * v * v +
    0.158137256 * v ** 3 +
    -6.57263143e-5 * t * v ** 3 +
    2.22697524e-7 * t * t * v ** 3 +
    -4.16117031e-8 * t ** 3 * v ** 3 +
    -0.0127762753 * v ** 4 +
    9.66891875e-6 * t * v ** 4 +
    2.52785852e-9 * t * t * v ** 4 +
    4.56306672e-4 * v ** 5 +
    -1.74202546e-7 * t * v ** 5 +
    -5.91491269e-6 * v ** 6 +
    0.398374029 * d +
    1.83945314e-4 * t * d +
    -1.7375451e-4 * t * t * d +
    -7.60781159e-7 * t ** 3 * d +
    3.77830287e-8 * t ** 4 * d +
    5.43079673e-10 * t ** 5 * d +
    -0.0200518269 * v * d +
    8.92859837e-4 * t * v * d +
    3.45433048e-6 * t * t * v * d +
    -3.77925774e-7 * t ** 3 * v * d +
    -1.69699377e-9 * t ** 4 * v * d +
    1.69992415e-4 * v * v * d +
    -4.99204314e-5 * t * v * v * d +
    2.47417178e-7 * t * t * v * v * d +
    1.07596466e-8 * t ** 3 * v * v * d +
    8.49242932e-5 * v ** 3 * d +
    1.35191328e-6 * t * v ** 3 * d +
    -6.21531254e-9 * t * t * v ** 3 * d +
    -4.99410301e-6 * v ** 4 * d +
    -1.89489258e-8 * t * v ** 4 * d +
    8.15300114e-8 * v ** 5 * d +
    7.5504309e-4 * d * d +
    -5.65095215e-5 * t * d * d +
    -4.52166564e-7 * t * t * d * d +
    2.46688878e-8 * t ** 3 * d * d +
    2.42674348e-10 * t ** 4 * d * d +
    1.5454725e-4 * v * d * d +
    5.2411097e-6 * t * v * d * d +
    -8.75874982e-8 * t * t * v * d * d +
    -1.50743064e-9 * t ** 3 * v * d * d +
    -1.56236307e-5 * v * v * d * d +
    -1.33895614e-7 * t * v * v * d * d +
    2.49709824e-9 * t * t * v * v * d * d +
    6.51711721e-7 * v ** 3 * d * d +
    1.94960053e-9 * t * v ** 3 * d * d +
    -1.00361113e-8 * v ** 4 * d * d +
    -1.21206673e-5 * d ** 3 +
    -2.1820366e-7 * t * d ** 3 +
    7.51269482e-9 * t * t * d ** 3 +
    9.79063848e-11 * t ** 3 * d ** 3 +
    1.25006734e-6 * v * d ** 3 +
    -1.81584736e-9 * t * v * d ** 3 +
    -3.52197671e-10 * t * t * v * d ** 3 +
    -3.3651463e-8 * v * v * d ** 3 +
    1.35908359e-10 * t * v * v * d ** 3 +
    4.1703262e-10 * v ** 3 * d ** 3 +
    -1.30369025e-9 * d ** 4 +
    4.13908461e-10 * t * d ** 4 +
    9.22652254e-12 * t * t * d ** 4 +
    -5.08220384e-9 * v * d ** 4 +
    -2.24730961e-11 * t * v * d ** 4 +
    1.17139133e-10 * v * v * d ** 4 +
    6.62154879e-10 * d ** 5 +
    4.0386326e-13 * t * d ** 5 +
    1.95087203e-12 * v * d ** 5 +
    -4.73602469e-12 * d ** 6 +
    5.12733497 * p +
    -0.312788561 * t * p +
    -0.0196701861 * t * t * p +
    9.9969087e-4 * t ** 3 * p +
    9.51738512e-6 * t ** 4 * p +
    -4.66426341e-7 * t ** 5 * p +
    0.548050612 * v * p +
    -0.00330552823 * t * v * p +
    -0.0016411944 * t * t * v * p +
    -5.16670694e-6 * t ** 3 * v * p +
    9.52692432e-7 * t ** 4 * v * p +
    -0.0429223622 * v * v * p +
    0.00500845667 * t * v * v * p +
    1.00601257e-6 * t * t * v * v * p +
    -1.81748644e-6 * t ** 3 * v * v * p +
    -1.25813502e-3 * v ** 3 * p +
    -1.79330391e-4 * t * v ** 3 * p +
    2.34994441e-6 * t * t * v ** 3 * p +
    1.29735808e-4 * v ** 4 * p +
    1.2906487e-6 * t * v ** 4 * p +
    -2.28558686e-6 * v ** 5 * p +
    -0.0369476348 * d * p +
    0.00162325322 * t * d * p +
    -3.1427968e-5 * t * t * d * p +
    2.59835559e-6 * t ** 3 * d * p +
    -4.77136523e-8 * t ** 4 * d * p +
    8.6420339e-3 * v * d * p +
    -6.87405181e-4 * t * v * d * p +
    -9.13863872e-6 * t * t * v * d * p +
    5.15916806e-7 * t ** 3 * v * d * p +
    -3.59217476e-5 * v * v * d * p +
    3.28696511e-5 * t * v * v * d * p +
    -7.10542454e-7 * t * t * v * v * d * p +
    -1.243823e-5 * v ** 3 * d * p +
    -7.385844e-9 * t * v ** 3 * d * p +
    2.20609296e-7 * v ** 4 * d * p +
    -7.3246918e-4 * d * d * p +
    -1.87381964e-5 * t * d * d * p +
    4.80925239e-6 * t * t * d * d * p +
    -8.7549204e-8 * t ** 3 * d * d * p +
    2.7786293e-5 * v * d * d * p +
    -5.06004592e-6 * t * v * d * d * p +
    1.14325367e-7 * t * t * v * d * d * p +
    2.53016723e-6 * v * v * d * d * p +
    -1.72857035e-8 * t * v * v * d * d * p +
    -3.95079398e-8 * v ** 3 * d * d * p +
    -3.59413173e-7 * d ** 3 * p +
    7.04388046e-7 * t * d ** 3 * p +
    -1.89309167e-8 * t * t * d ** 3 * p +
    -4.79768731e-7 * v * d ** 3 * p +
    7.96079978e-9 * t * v * d ** 3 * p +
    1.62897058e-9 * v * v * d ** 3 * p +
    3.94367674e-8 * d ** 4 * p +
    -1.18566247e-9 * t * d ** 4 * p +
    3.34678041e-10 * v * d ** 4 * p +
    -1.15606447e-10 * d ** 5 * p +
    -2.80626406 * p * p +
    0.548712484 * t * p * p +
    -0.0039942841 * t * t * p * p +
    -9.54009191e-4 * t ** 3 * p * p +
    1.93090978e-5 * t ** 4 * p * p +
    -0.308806365 * v * p * p +
    0.0116952364 * t * v * p * p +
    4.95271903e-4 * t * t * v * p * p +
    -1.90710882e-5 * t ** 3 * v * p * p +
    0.00210787756 * v * v * p * p +
    -6.98445738e-4 * t * v * v * p * p +
    2.30109073e-5 * t * t * v * v * p * p +
    4.1785659e-4 * v ** 3 * p * p +
    -1.27043871e-5 * t * v ** 3 * p * p +
    -3.04620472e-6 * v ** 4 * p * p +
    0.0514507424 * d * p * p +
    -0.00432510997 * t * d * p * p +
    8.99281156e-5 * t * t * d * p * p +
    -7.14663943e-7 * t ** 3 * d * p * p +
    -2.66016305e-4 * v * d * p * p +
    2.63789586e-4 * t * v * d * p * p +
    -7.01199003e-6 * t * t * v * d * p * p +
    -1.06823306e-4 * v * v * d * p * p +
    3.61341136e-6 * t * v * v * d * p * p +
    2.29748967e-7 * v ** 3 * d * p * p +
    3.04788893e-4 * d * d * p * p +
    -6.42070836e-5 * t * d * d * p * p +
    1.16257971e-6 * t * t * d * d * p * p +
    7.68023384e-6 * v * d * d * p * p +
    -5.47446896e-7 * t * v * d * d * p * p +
    -3.5993791e-8 * v * v * d * d * p * p +
    -4.36497725e-6 * d ** 3 * p * p +
    1.68737969e-7 * t * d ** 3 * p * p +
    2.67489271e-8 * v * d ** 3 * p * p +
    3.23926897e-9 * d ** 4 * p * p +
    -0.0353874123 * p ** 3 +
    -0.22120119 * t * p ** 3 +
    0.0155126038 * t * t * p ** 3 +
    -2.63917279e-4 * t ** 3 * p ** 3 +
    0.0453433455 * v * p ** 3 +
    -0.00432943862 * t * v * p ** 3 +
    1.45389826e-4 * t * t * v * p ** 3 +
    2.1750861e-4 * v * v * p ** 3 +
    -6.66724702e-5 * t * v * v * p ** 3 +
    3.3321714e-5 * v ** 3 * p ** 3 +
    -0.00226921615 * d * p ** 3 +
    3.80261982e-4 * t * d * p ** 3 +
    -5.45314314e-9 * t * t * d * p ** 3 +
    -7.96355448e-4 * v * d * p ** 3 +
    2.53458034e-5 * t * v * d * p ** 3 +
    -6.31223658e-6 * v * v * d * p ** 3 +
    3.02122035e-4 * d * d * p ** 3 +
    -4.77403547e-6 * t * d * d * p ** 3 +
    1.73825715e-6 * v * d * d * p ** 3 +
    -4.09087898e-7 * d ** 3 * p ** 3 +
    0.614155345 * p ** 4 +
    -0.0616755931 * t * p ** 4 +
    0.00133374846 * t * t * p ** 4 +
    0.00355375387 * v * p ** 4 +
    -5.13027851e-4 * t * v * p ** 4 +
    1.02449757e-4 * v * v * p ** 4 +
    -0.00148526421 * d * p ** 4 +
    -4.11469183e-5 * t * d * p ** 4 +
    -6.80434415e-6 * v * d * p ** 4 +
    -9.77675906e-6 * d * d * p ** 4 +
    0.0882773108 * p ** 5 +
    -0.00301859306 * t * p ** 5 +
    0.00104452989 * v * p ** 5 +
    2.47090539e-4 * d * p ** 5 +
    0.00148348065 * p ** 6
  )
}

// Each [threshold, category] pair means "this category's range ends at
// threshold" (upper-bound inclusive) - matches the official UTCI
// category definitions and src/weather/heat_stress.py exactly. See that
// file's comment for why the opposite convention is wrong.
function utciStressCategory(utciC: number): string {
  for (const [threshold, category] of UTCI_STRESS_CATEGORIES) {
    if (utciC <= threshold) return category
  }
  return 'extreme heat stress'
}

export interface HeatStressResult {
  heatIndexC: number | null
  wbgtShadeC: number
  meanRadiantTempC: number
  utciC: number
  utciStressCategory: string
}

export function calculateHeatStress(
  tempC: number,
  relativeHumidity: number,
  windSpeedMs: number,
  solarRadiationWm2: number
): HeatStressResult {
  const heatIndexC = calculateHeatIndex(tempC, relativeHumidity)
  const wbgtShadeC = calculateWbgtShade(tempC, relativeHumidity)
  const meanRadiantTempC = estimateMeanRadiantTemperature(tempC, solarRadiationWm2)

  const clippedWind = Math.min(Math.max(windSpeedMs, UTCI_MIN_WIND_MS), UTCI_MAX_WIND_MS)
  const deltaTr = meanRadiantTempC - tempC
  const vapourPressureKpa = (saturationVapourPressureHpa(tempC) * (relativeHumidity / 100)) / 10

  const utciC = utciPolynomial(tempC, clippedWind, deltaTr, vapourPressureKpa)

  return {
    heatIndexC: heatIndexC === null ? null : Math.round(heatIndexC * 10) / 10,
    wbgtShadeC: Math.round(wbgtShadeC * 100) / 100,
    meanRadiantTempC: Math.round(meanRadiantTempC * 100) / 100,
    utciC: Math.round(utciC * 10) / 10,
    utciStressCategory: utciStressCategory(utciC),
  }
}
