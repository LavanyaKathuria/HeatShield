import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

import en from './locales/en.json'
import hi from './locales/hi.json'
import gu from './locales/gu.json'

// NOTE: hi/gu translations here are a first pass for demo purposes -
// have a native Hindi/Gujarati speaker review them before any real
// deployment. Machine-translating emergency health advisories carries
// real risk (see project notes); these were written by hand with care
// but not native-reviewed.
i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      hi: { translation: hi },
      gu: { translation: gu },
    },
    fallbackLng: 'en',
    interpolation: { escapeValue: false },
  })

export default i18n
