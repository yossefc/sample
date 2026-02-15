/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        he: ['Heebo', 'Arial', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
