import '@mdi/font/css/materialdesignicons.css'
import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

const modernTheme = {
    dark: true,
    colors: {
        background: '#000000',
        surface: '#000000',
        primary: '#6366f1',
        'primary-darken-1': '#4338ca',
        secondary: '#10b981',
        'secondary-darken-1': '#059669',
        error: '#ef4444',
        info: '#3b82f6',
        success: '#10b981',
        warning: '#f59e0b',
    },
}

export default createVuetify({
    components,
    directives,
    theme: {
        defaultTheme: 'modernTheme',
        themes: {
            modernTheme,
        },
    },
})
