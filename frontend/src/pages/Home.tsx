import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { Product, News } from '../lib/types';
import { formatPrice } from '../lib/utils';
import { Button } from '../components/ui/Button';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { ShoppingCart, ArrowRight, Star, TrendingUp } from 'lucide-react';

export function Home() {
  const { data: products, isLoading: productsLoading } = useQuery({
    queryKey: ['products', { limit: 8 }],
    queryFn: async () => {
      const response = await api.get('/products?limit=8');
      return response.data as Product[];
    },
  });

  const { data: news, isLoading: newsLoading } = useQuery({
    queryKey: ['news', { limit: 3 }],
    queryFn: async () => {
      const response = await api.get('/news?limit=3');
      return response.data as News[];
    },
  });

  return (
    <div className="space-y-16">
      {/* Hero Section */}
      <section className="bg-gradient-to-r from-primary-600 to-primary-800 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <div className="text-center space-y-8">
            <h1 className="text-4xl md:text-6xl font-bold text-balance">
              Chào mừng đến với TamStore
            </h1>
            <p className="text-xl md:text-2xl text-primary-100 max-w-3xl mx-auto text-balance">
              Khám phá hàng ngàn sản phẩm chất lượng cao với giá cả hợp lý và dịch vụ tuyệt vời
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button
                size="lg"
                className="bg-white text-primary-600 hover:bg-gray-100"
                onClick={() => window.location.href = '/products'}
              >
                Khám phá sản phẩm
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
              <Button
                variant="ghost"
                size="lg"
                className="border-2 border-white text-white hover:bg-white hover:text-primary-600"
                onClick={() => window.location.href = '/chatbot'}
              >
                Hỗ trợ trực tuyến
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Featured Products */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold text-gray-900 mb-4">Sản phẩm nổi bật</h2>
          <p className="text-lg text-gray-600">Những sản phẩm được yêu thích nhất</p>
        </div>

        {productsLoading ? (
          <div className="flex justify-center py-12">
            <LoadingSpinner size="lg" />
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {products?.map((product) => (
              <div
                key={product.id}
                className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-lg transition-shadow duration-300 group"
              >
                <div className="aspect-square bg-gray-100 relative overflow-hidden">
                  {product.image_url ? (
                    <img
                      src={product.image_url}
                      alt={product.name}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <ShoppingCart className="h-12 w-12 text-gray-400" />
                    </div>
                  )}
                  <div className="absolute top-2 right-2">
                    <div className="bg-primary-600 text-white px-2 py-1 rounded-full text-xs font-medium">
                      Mới
                    </div>
                  </div>
                </div>
                <div className="p-4">
                  <h3 className="font-semibold text-gray-900 mb-2 line-clamp-2">
                    {product.name}
                  </h3>
                  <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                    {product.description}
                  </p>
                  <div className="flex items-center justify-between">
                    <span className="text-lg font-bold text-primary-600">
                      {formatPrice(product.price)}
                    </span>
                    <div className="flex items-center space-x-1">
                      <Star className="h-4 w-4 text-yellow-400 fill-current" />
                      <span className="text-sm text-gray-600">4.5</span>
                    </div>
                  </div>
                  <Link
                    to={`/products/${product.id}`}
                    className="mt-3 w-full btn-primary block text-center"
                  >
                    Xem chi tiết
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="text-center">
          <Link to="/products">
            <Button size="lg">
              Xem tất cả sản phẩm
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="bg-gray-50 py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">Tại sao chọn TamStore?</h2>
            <p className="text-lg text-gray-600">Những lý do khiến khách hàng tin tưởng chúng tôi</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="text-center space-y-4">
              <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto">
                <ShoppingCart className="h-8 w-8 text-primary-600" />
              </div>
              <h3 className="text-xl font-semibold text-gray-900">Sản phẩm chất lượng</h3>
              <p className="text-gray-600">
                Tất cả sản phẩm đều được kiểm tra kỹ lưỡng trước khi đến tay khách hàng
              </p>
            </div>

            <div className="text-center space-y-4">
              <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto">
                <TrendingUp className="h-8 w-8 text-primary-600" />
              </div>
              <h3 className="text-xl font-semibold text-gray-900">Giá cả hợp lý</h3>
              <p className="text-gray-600">
                Cam kết mang đến những sản phẩm tốt nhất với mức giá cạnh tranh nhất
              </p>
            </div>

            <div className="text-center space-y-4">
              <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto">
                <Star className="h-8 w-8 text-primary-600" />
              </div>
              <h3 className="text-xl font-semibold text-gray-900">Dịch vụ tuyệt vời</h3>
              <p className="text-gray-600">
                Đội ngũ hỗ trợ khách hàng 24/7 luôn sẵn sàng giải đáp mọi thắc mắc
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Latest News */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold text-gray-900 mb-4">Tin tức mới nhất</h2>
          <p className="text-lg text-gray-600">Cập nhật những thông tin hữu ích</p>
        </div>

        {newsLoading ? (
          <div className="flex justify-center py-12">
            <LoadingSpinner size="lg" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
            {news?.map((article) => (
              <article
                key={article.id}
                className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-lg transition-shadow duration-300"
              >
                <div className="aspect-video bg-gray-100 relative overflow-hidden">
                  {article.image_url ? (
                    <img
                      src={article.image_url}
                      alt={article.title}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <div className="text-gray-400">Không có hình ảnh</div>
                    </div>
                  )}
                </div>
                <div className="p-6">
                  <h3 className="font-semibold text-gray-900 mb-2 line-clamp-2">
                    {article.title}
                  </h3>
                  <p className="text-gray-600 text-sm mb-4 line-clamp-3">
                    {article.content}
                  </p>
                  <Link
                    to={`/news/${article.id}`}
                    className="text-primary-600 hover:text-primary-700 font-medium text-sm"
                  >
                    Đọc thêm →
                  </Link>
                </div>
              </article>
            ))}
          </div>
        )}

        <div className="text-center">
          <Link to="/news">
            <Button variant="secondary" size="lg">
              Xem tất cả tin tức
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
          </Link>
        </div>
      </section>
    </div>
  );
}